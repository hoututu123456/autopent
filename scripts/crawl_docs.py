import argparse
import hashlib
import json
import os
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class CrawlTarget:
    name: str
    seeds: List[str]
    allowed_hosts: Set[str]
    allowed_path_prefixes: List[str]
    default_category: str
    sitemap_paths: Optional[List[str]] = None


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha1(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def _slugify(text: str, max_len: int = 64) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = "doc"
    return s[:max_len]


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
    cleaned = urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            path,
            parsed.query,
            "",
        )
    )
    return cleaned


def _is_same_host(url: str, allowed_hosts: Set[str]) -> bool:
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except Exception:
        return False
    host = host.lower()
    return host in {h.lower() for h in allowed_hosts}


def _path_allowed(url: str, prefixes: List[str]) -> bool:
    try:
        p = urllib.parse.urlsplit(url).path or "/"
    except Exception:
        return False
    p = p.lower()
    if not prefixes:
        return True
    for pref in prefixes:
        if p.startswith((pref or "").lower()):
            return True
    return False


def _looks_like_html_response(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return "text/html" in ct or "application/xhtml" in ct


def _extract_links(base_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    out = []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        joined = urllib.parse.urljoin(base_url, href)
        try:
            joined = _normalize_url(joined)
        except Exception:
            continue
        out.append(joined)
    return out


def _pick_main_container(soup: BeautifulSoup):
    main = soup.find("main")
    if main:
        return main
    article = soup.find("article")
    if article:
        return article
    body = soup.body
    return body or soup


def _strip_noise(container):
    for tag in container.find_all(["script", "style", "noscript", "svg"]):
        try:
            tag.decompose()
        except Exception:
            pass
    for tag in container.find_all(["header", "footer", "nav", "aside", "form"]):
        try:
            tag.decompose()
        except Exception:
            pass


def html_to_markdown(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    title = ""
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)

    container = _pick_main_container(soup)
    _strip_noise(container)

    lines: List[str] = []
    seen = 0
    for el in container.descendants:
        if getattr(el, "name", None) in {"h1", "h2", "h3"}:
            text = el.get_text(" ", strip=True)
            if text:
                level = {"h1": "#", "h2": "##", "h3": "###"}[el.name]
                lines.append(f"{level} {text}")
                lines.append("")
                seen += 1
        elif getattr(el, "name", None) == "pre":
            code = el.get_text("\n", strip=False)
            code = (code or "").rstrip("\n")
            if code.strip():
                lines.append("```")
                lines.append(code)
                lines.append("```")
                lines.append("")
                seen += 1
        elif getattr(el, "name", None) == "p":
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")
                seen += 1
        elif getattr(el, "name", None) in {"ul", "ol"}:
            items = el.find_all("li", recursive=False)
            for li in items:
                t = li.get_text(" ", strip=True)
                if t:
                    lines.append(f"- {t}")
                    seen += 1
            if items:
                lines.append("")

        if seen > 4000:
            break

    text = "\n".join([ln.rstrip() for ln in lines]).strip()
    if len(text) < 200:
        raw = container.get_text("\n", strip=True) if container else ""
        raw_lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]
        text = "\n".join(raw_lines)
    text = (text or "").strip() + "\n"
    if not title:
        first_h = container.find(["h1", "h2"])
        if first_h:
            title = first_h.get_text(" ", strip=True)
    title = (title or "").strip()
    return title, text


_REDACT_PATTERNS = [
    r"\bmsfvenom\b",
    r"\bmeterpreter\b",
    r"\breverse[_\-\s]*shell\b",
    r"\bshellcode\b",
    r"\bpayload\b",
    r"\bnc\s+-e\b",
    r"\bncat\s+--exec\b",
    r"\bbash\s+-i\b",
    r"\bpython\s+-c\b.*socket",
    r"\bpowershell\b.*-enc\b",
    r"\bInvoke-Expression\b|\bIEX\b",
]


def sanitize_markdown(md_text: str) -> Tuple[str, int]:
    text = md_text or ""
    redactions = 0
    in_code = False
    buf: List[str] = []
    code_buf: List[str] = []
    compiled = [re.compile(p, re.IGNORECASE) for p in _REDACT_PATTERNS]

    def flush_code_block():
        nonlocal redactions, code_buf
        block = "\n".join(code_buf)
        if any(p.search(block) for p in compiled):
            buf.append("[REDACTED: potential weaponization content removed]")
            redactions += 1
        else:
            buf.extend(code_buf)
        code_buf = []

    for line in text.splitlines():
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = [line]
            else:
                code_buf.append(line)
                flush_code_block()
                in_code = False
            continue
        if in_code:
            code_buf.append(line)
        else:
            buf.append(line)

    if in_code and code_buf:
        flush_code_block()

    return "\n".join(buf).strip() + "\n", redactions


def categorize_doc(target: CrawlTarget, url: str, title: str, md_text: str) -> str:
    u = url.lower()
    t = (title or "").lower()

    if "ssa.to" in u:
        if "/syntaxflow-guide/" in u:
            return "skills"
        if any(k in t for k in ["guide", "quick start", "入门", "指南", "教程", "advanced", "实战"]):
            return "skills"
        return "knowledge"

    if "yaklang.com" in u:
        if "/products/" in u:
            return "skills"
        if "/yaklab/wiki/" in u:
            return "skills"
        if "/yaklab/" in u:
            if any(k in t for k in ["install", "安装", "使用", "实践", "指南", "案例", "example"]):
                return "skills"
            return target.default_category
        return target.default_category

    return target.default_category


def build_filename(prefix: str, url: str, title: str) -> str:
    slug = _slugify(title) if title else _slugify(urllib.parse.urlsplit(url).path.strip("/").replace("/", "_"))
    h = _sha1(url)[:8]
    return f"{prefix}_{slug}_{h}.md"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_markdown(out_dir: str, filename: str, url: str, title: str, md_text: str) -> str:
    ensure_dir(out_dir)
    front = [
        f"# {title}" if title else "# 文档",
        "",
        f"- 来源: {url}",
        f"- 抓取时间: {_now_iso()}",
        "",
        "---",
        "",
    ]
    content = "\n".join(front) + md_text
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def fetch_robots_txt(client: httpx.Client, base: str) -> str:
    parsed = urllib.parse.urlsplit(base)
    robots = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        r = client.get(robots)
        if r.status_code == 200 and r.text:
            return r.text
    except Exception:
        return ""
    return ""

def _sitemap_url_from_seed(seed: str) -> str:
    parsed = urllib.parse.urlsplit(seed)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/sitemap.xml", "", ""))


def fetch_sitemap_urls(
    client: httpx.Client,
    seed: str,
    sitemap_paths: Optional[List[str]] = None,
    max_sitemaps: int = 20,
    max_urls: int = 50000,
) -> List[str]:
    parsed = urllib.parse.urlsplit(seed)
    paths = sitemap_paths or ["/sitemap.xml"]
    to_fetch = [
        urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, p if p.startswith("/") else ("/" + p), "", ""))
        for p in paths
    ]
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

        text = r.text or ""
        is_index = "<sitemapindex" in text[:2000].lower()
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text, flags=re.IGNORECASE)
        if not locs:
            continue
        if is_index:
            for u in locs:
                if u not in fetched and u not in to_fetch and len(to_fetch) < max_sitemaps:
                    to_fetch.append(u)
            continue

        for u in locs:
            try:
                u = _normalize_url(u)
            except Exception:
                continue
            urls.append(u)
            if len(urls) >= max_urls:
                break

    return urls

def parse_robots_disallows(robots_text: str) -> List[str]:
    disallows: List[str] = []
    current_applies = False
    for raw in (robots_text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().lower()
        v = v.strip()
        if k == "user-agent":
            current_applies = v == "*" or v.lower() == "autopentestai"
        elif k == "disallow" and current_applies:
            if v:
                disallows.append(v)
    return disallows


def robots_allows(url: str, disallows: List[str]) -> bool:
    path = urllib.parse.urlsplit(url).path or "/"
    for d in disallows or []:
        if d == "/":
            return False
        if path.startswith(d):
            return False
    return True


def crawl(
    target: CrawlTarget,
    out_skills_dir: str,
    out_kb_dir: str,
    max_pages: int,
    delay_ms: int,
    state_path: Optional[str] = None,
    user_agent: str = "AutoPentestAI-DocCrawler/1.0",
    insecure: bool = False,
    overwrite: bool = False,
) -> Dict:
    visited: Set[str] = set()
    queue: List[str] = []
    saved: List[Dict] = []

    if state_path and os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                st = json.load(f) or {}
            visited = set(st.get("visited") or [])
            queue = list(st.get("queue") or [])
        except Exception:
            visited = set()
            queue = []

    for s in target.seeds:
        try:
            u = _normalize_url(s)
        except Exception:
            continue
        if u not in visited and u not in queue:
            queue.append(u)

    proxy_url = (os.getenv("PROXY_URL") or "").strip()
    client_kwargs = {"timeout": 25.0, "follow_redirects": True, "headers": {"User-Agent": user_agent}, "verify": (not insecure)}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with httpx.Client(**client_kwargs) as client:
        robots_text = fetch_robots_txt(client, target.seeds[0])
        disallows = parse_robots_disallows(robots_text)
        sitemap_added = 0

        try:
            sitemap_urls = fetch_sitemap_urls(
                client,
                target.seeds[0],
                sitemap_paths=target.sitemap_paths,
                max_sitemaps=20,
                max_urls=50000,
            )
        except Exception:
            sitemap_urls = []
        for u in sitemap_urls:
            if u in visited or u in queue:
                continue
            if not _is_same_host(u, target.allowed_hosts):
                continue
            if not _path_allowed(u, target.allowed_path_prefixes):
                continue
            if not robots_allows(u, disallows):
                continue
            queue.append(u)
            sitemap_added += 1

        while queue and len(saved) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if not _is_same_host(url, target.allowed_hosts):
                continue
            if not _path_allowed(url, target.allowed_path_prefixes):
                continue
            if not robots_allows(url, disallows):
                continue

            try:
                r = client.get(url)
            except Exception:
                continue

            if r.status_code < 200 or r.status_code >= 300:
                continue
            if not _looks_like_html_response(r.headers.get("content-type", "")):
                continue

            html = r.text or ""
            title, md_text = html_to_markdown(html)
            if not md_text.strip():
                if title:
                    md_text = "（正文提取为空：该页面可能主要由前端动态渲染，或内容在当前抓取条件下不可见。）\n"
                else:
                    continue
            md_text, redacted = sanitize_markdown(md_text)

            category = categorize_doc(target, url, title, md_text)
            prefix = "SSA" if "ssa.to" in url.lower() else ("YakLab" if "yaklang.com" in url.lower() else target.name)
            filename = build_filename(prefix, url, title)
            out_dir = out_skills_dir if category == "skills" else out_kb_dir
            path = os.path.join(out_dir, filename)
            if overwrite or not os.path.exists(path):
                path = save_markdown(out_dir, filename, url, title, md_text)

            saved.append({"url": url, "title": title, "category": category, "file": path, "redacted_blocks": redacted})

            base_for_links = str(getattr(r, "url", url))
            for link in _extract_links(base_for_links, html):
                if link in visited:
                    continue
                if not _is_same_host(link, target.allowed_hosts):
                    continue
                if not _path_allowed(link, target.allowed_path_prefixes):
                    continue
                if link not in queue:
                    queue.append(link)

            if state_path:
                try:
                    ensure_dir(os.path.dirname(state_path))
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump({"visited": sorted(visited), "queue": queue}, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    return {
        "target": target.name,
        "saved": saved,
        "saved_count": len(saved),
        "visited_count": len(visited),
        "queue_remaining": len(queue),
        "max_pages": int(max_pages),
        "max_reached": len(saved) >= int(max_pages),
        "robots_disallows": len(disallows),
        "sitemap_urls_added": sitemap_added,
    }


def _default_targets() -> List[CrawlTarget]:
    return [
        CrawlTarget(
            name="YakLab",
            seeds=[
                "https://www.yaklang.com/Yaklab/yaklab",
                "https://yaklang.com/en/Yaklab/yaklab/",
                "https://yaklang.com/en/Yaklab/vulinbox/vulinbox/",
            ],
            allowed_hosts={"yaklang.com", "www.yaklang.com"},
            allowed_path_prefixes=["/yaklab/", "/en/yaklab/", "/products/", "/en/products/"],
            default_category="skills",
            sitemap_paths=["/sitemap.xml"],
        ),
        CrawlTarget(
            name="SSA",
            seeds=[
                "https://ssa.to/en/",
                "https://ssa.to/en/syntaxflow-guide/intro",
                "https://ssa.to/en/syntaxflow-guide/quick-start",
            ],
            allowed_hosts={"ssa.to"},
            allowed_path_prefixes=[
                "/en/",
                "/docs/",
                "/syntaxflow-guide/",
                "/static-analysis-guide/",
                "/codeanalysis",
                "/cookbook",
                "/search",
                "/markdown-page",
            ],
            default_category="knowledge",
            sitemap_paths=["/sitemap.xml"],
        ),
    ]


def load_targets_from_config(path: str) -> List[CrawlTarget]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f) or {}
    targets = []
    for t in cfg.get("targets") or []:
        targets.append(
            CrawlTarget(
                name=str(t.get("name") or "Target"),
                seeds=list(t.get("seeds") or []),
                allowed_hosts=set(t.get("allowed_hosts") or []),
                allowed_path_prefixes=list(t.get("allowed_path_prefixes") or []),
                default_category=str(t.get("default_category") or "knowledge"),
                sitemap_paths=list(t.get("sitemap_paths") or []) or ["/sitemap.xml"],
            )
        )
    return targets



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="all", choices=["all", "yaklab", "ssa"], help="要爬取的目标站点")
    ap.add_argument("--max-pages", type=int, default=200, help="最多保存页面数（每个 target 单独计数）")
    ap.add_argument("--delay-ms", type=int, default=300, help="请求间隔（毫秒）")
    ap.add_argument("--skills-dir", default="data/skills", help="skills 输出目录")
    ap.add_argument("--knowledge-dir", default="data/knowledge", help="knowledge 输出目录")
    ap.add_argument("--state-dir", default="data/temp/crawl_state", help="断点续爬状态目录")
    ap.add_argument("--index-file", default="data/temp/crawl_index.json", help="输出索引文件（JSON）")
    ap.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验（仅在本机证书缺失导致无法访问时使用）")
    ap.add_argument("--overwrite", action="store_true", help="覆盖已存在的同名落盘文件")
    ap.add_argument("--config", default="", help="自定义抓取配置 JSON（包含 targets 列表）")
    args = ap.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    skills_dir = os.path.join(base_dir, args.skills_dir)
    kb_dir = os.path.join(base_dir, args.knowledge_dir)
    state_dir = os.path.join(base_dir, args.state_dir)
    index_file = os.path.join(base_dir, args.index_file)
    ensure_dir(state_dir)
    ensure_dir(os.path.dirname(index_file))

    targets = load_targets_from_config(os.path.join(base_dir, args.config)) if args.config else _default_targets()
    selected: List[CrawlTarget] = []
    if args.target == "all":
        selected = targets
    elif args.target == "yaklab":
        selected = [t for t in targets if t.name.lower() == "yaklab"]
    else:
        selected = [t for t in targets if t.name.lower() == "ssa"]

    index: Dict[str, Dict] = {}
    for t in selected:
        state_path = os.path.join(state_dir, f"{t.name.lower()}_state.json")
        res = crawl(
            t,
            out_skills_dir=skills_dir,
            out_kb_dir=kb_dir,
            max_pages=max(1, args.max_pages),
            delay_ms=max(0, args.delay_ms),
            state_path=state_path,
            insecure=bool(args.insecure),
            overwrite=bool(args.overwrite),
        )
        index[t.name] = res

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(json.dumps(index, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
