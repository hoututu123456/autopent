import argparse
import json
import os
import re
import time
import urllib.parse
from typing import Dict, List, Optional, Set, Tuple

import httpx


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    parsed = urllib.parse.urlsplit(u)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("invalid_scheme")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


def _sitemap_url(base: str, path: str = "/sitemap.xml") -> str:
    parsed = urllib.parse.urlsplit(base)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _extract_locs(xml_text: str) -> List[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text or "", flags=re.IGNORECASE)


def fetch_sitemap_urls(
    client: httpx.Client,
    sitemap_url: str,
    max_sitemaps: int = 30,
    max_urls: int = 200000,
) -> List[str]:
    to_fetch = [sitemap_url]
    fetched = set()
    urls: List[str] = []

    while to_fetch and len(fetched) < max_sitemaps and len(urls) < max_urls:
        sm = to_fetch.pop(0)
        if sm in fetched:
            continue
        fetched.add(sm)

        try:
            r = client.get(sm)
        except Exception:
            continue
        if r.status_code != 200 or not r.text:
            continue

        text = r.text
        is_index = "<sitemapindex" in text[:2000].lower()
        locs = _extract_locs(text)
        if not locs:
            continue

        if is_index:
            for u in locs:
                u = u.strip()
                if u and u not in fetched and u not in to_fetch and len(to_fetch) < max_sitemaps:
                    to_fetch.append(u)
            continue

        for u in locs:
            try:
                urls.append(_normalize_url(u))
            except Exception:
                continue
            if len(urls) >= max_urls:
                break

    return urls


def _path_allowed(url: str, prefixes: List[str]) -> bool:
    p = (urllib.parse.urlsplit(url).path or "/").lower()
    if not prefixes:
        return True
    return any(p.startswith((pref or "").lower()) for pref in prefixes)


def _load_index(index_path: str) -> Dict:
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f) or {}


def _collect_saved_urls(index: Dict) -> Set[str]:
    saved = set()
    for target_data in (index or {}).values():
        for item in target_data.get("saved") or []:
            u = item.get("url")
            if not u:
                continue
            try:
                saved.add(_normalize_url(u))
            except Exception:
                continue
    return saved


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-file", default="data/temp/crawl_index.json")
    ap.add_argument("--out-md", default="data/temp/crawl_coverage.md")
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--max-urls", type=int, default=200000)
    args = ap.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    index_path = os.path.join(base_dir, args.index_file)
    out_md = os.path.join(base_dir, args.out_md)
    os.makedirs(os.path.dirname(out_md), exist_ok=True)

    index = _load_index(index_path) if os.path.exists(index_path) else {}
    saved_urls = _collect_saved_urls(index)

    proxy_url = (os.getenv("PROXY_URL") or "").strip()
    client_kwargs = {"timeout": 30.0, "follow_redirects": True, "verify": (not args.insecure)}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    sites = [
        {
            "name": "YakLab/Yakit (yaklang.com)",
            "bases": ["https://yaklang.com", "https://www.yaklang.com"],
            "prefixes": ["/yaklab/", "/en/yaklab/", "/products/", "/en/products/"],
            "candidate_sitemaps": ["/sitemap.xml"],
        },
        {
            "name": "SSA.to",
            "bases": ["https://ssa.to"],
            "prefixes": ["/en/"],
            "candidate_sitemaps": ["/sitemap.xml", "/en/sitemap.xml"],
        },
    ]

    report = {"generated_at": _now_iso(), "index_file": args.index_file, "sites": []}

    with httpx.Client(**client_kwargs) as client:
        for s in sites:
            all_urls: Set[str] = set()
            for base in s["bases"]:
                for sm_path in s["candidate_sitemaps"]:
                    sm_url = _sitemap_url(base, sm_path)
                    urls = fetch_sitemap_urls(client, sm_url, max_sitemaps=30, max_urls=args.max_urls)
                    for u in urls:
                        all_urls.add(u)

            in_scope = {u for u in all_urls if _path_allowed(u, s["prefixes"])}
            covered = {u for u in in_scope if u in saved_urls}
            missing = sorted(list(in_scope - covered))

            coverage = 0.0
            if in_scope:
                coverage = round((len(covered) / len(in_scope)) * 100.0, 2)

            report["sites"].append(
                {
                    "name": s["name"],
                    "sitemap_urls_total": len(all_urls),
                    "sitemap_urls_in_scope": len(in_scope),
                    "saved_urls_covered": len(covered),
                    "coverage_percent": coverage,
                    "missing_count": len(missing),
                    "missing_sample": missing[:30],
                }
            )

    md_lines = []
    md_lines.append("# 抓取覆盖率报告")
    md_lines.append("")
    md_lines.append(f"- 生成时间: {report['generated_at']}")
    md_lines.append(f"- 索引文件: `{report['index_file']}`")
    md_lines.append("")
    for s in report["sites"]:
        md_lines.append(f"## {s['name']}")
        md_lines.append(f"- Sitemap 总 URL: {s['sitemap_urls_total']}")
        md_lines.append(f"- 在白名单范围内 URL: {s['sitemap_urls_in_scope']}")
        md_lines.append(f"- 已落盘覆盖 URL: {s['saved_urls_covered']}")
        md_lines.append(f"- 覆盖率: {s['coverage_percent']}%")
        md_lines.append(f"- 缺口数: {s['missing_count']}")
        if s["missing_sample"]:
            md_lines.append("")
            md_lines.append("缺口样例（前 30 条）：")
            for u in s["missing_sample"]:
                md_lines.append(f"- {u}")
        md_lines.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines).rstrip() + "\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
