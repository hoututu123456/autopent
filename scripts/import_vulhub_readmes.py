import argparse
import os
import re
from typing import Iterable, List, Tuple


_REDACT_PATTERNS = [
    r"\bmsfvenom\b",
    r"\bmsfconsole\b",
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
    r"\bldap://\b|\brmi://\b",
    r"\b\$\{jndi:",
    r"\bysoserial\b",
]

_CODEBLOCK_ALLOWLIST = [
    r"^\s*(docker\s+compose|docker-compose)\s+",
    r"^\s*docker\s+(run|build|pull|login)\s+",
    r"^\s*git\s+clone\s+",
    r"^\s*cd\s+",
]


def _read_text(path: str, max_chars: int = 2_000_000) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        s = f.read(max_chars + 1)
    if len(s) > max_chars:
        s = s[:max_chars]
    return s


def sanitize_markdown(md: str) -> Tuple[str, int]:
    text = md or ""
    compiled = [re.compile(p, re.IGNORECASE) for p in _REDACT_PATTERNS]
    allow = [re.compile(p, re.IGNORECASE) for p in _CODEBLOCK_ALLOWLIST]
    in_code = False
    code_buf: List[str] = []
    out: List[str] = []
    redacted = 0

    def flush_code():
        nonlocal redacted, code_buf
        block = "\n".join(code_buf)
        code_lines = [ln for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("```")]
        allow_ok = False
        if code_lines and all(any(a.search(ln) for a in allow) for ln in code_lines):
            allow_ok = True
        if (not allow_ok) or any(p.search(block) for p in compiled):
            out.append("[REDACTED: potential weaponization content removed]")
            redacted += 1
        else:
            out.extend(code_buf)
        code_buf = []

    for line in text.splitlines():
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = [line]
            else:
                code_buf.append(line)
                flush_code()
                in_code = False
            continue
        if in_code:
            code_buf.append(line)
        else:
            out.append(line)

    if in_code and code_buf:
        flush_code()
    return "\n".join(out).strip() + "\n", redacted


def _slugify(text: str, max_len: int = 80) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s or "vulhub")[:max_len]


def _extract_cves(text: str) -> List[str]:
    cves = re.findall(r"\bCVE-\d{4}-\d{4,7}\b", text or "", flags=re.IGNORECASE)
    uniq = []
    seen = set()
    for c in cves:
        c_up = c.upper()
        if c_up in seen:
            continue
        seen.add(c_up)
        uniq.append(c_up)
    return uniq[:20]


def _iter_readmes(vulhub_root: str) -> Iterable[str]:
    ignore_parts = {".git", ".github", "tests", "base", "docs", ".vscode"}
    for dirpath, dirnames, filenames in os.walk(vulhub_root):
        dirnames[:] = [d for d in dirnames if d not in ignore_parts]
        for fn in filenames:
            if fn.lower() in {"readme.md", "readme.zh-cn.md"}:
                yield os.path.join(dirpath, fn)


def _title_from_rel(rel_dir: str) -> str:
    parts = [p for p in rel_dir.replace("\\", "/").split("/") if p]
    if not parts:
        return "Vulhub"
    if len(parts) >= 2:
        return f"{parts[-2]} / {parts[-1]}"
    return parts[-1]


def _write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="vulhub 根目录路径")
    ap.add_argument("--dest", default="data/vulndb/vulhub", help="输出目录（相对 AutoPentestAI 根）")
    ap.add_argument("--index", default="data/vulndb/Vulhub_README_Index.md", help="索引文件（相对 AutoPentestAI 根）")
    ap.add_argument("--overwrite", action="store_true", help="覆盖已存在文件")
    ap.add_argument("--max-files", type=int, default=100000)
    args = ap.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_root = os.path.abspath(args.src)
    dest_root = os.path.join(base_dir, args.dest)
    index_path = os.path.join(base_dir, args.index)

    entries: List[Dict] = []
    imported = 0

    for fp in _iter_readmes(src_root):
        if imported >= args.max_files:
            break
        rel = os.path.relpath(fp, src_root)
        rel_norm = rel.replace("\\", "/")
        rel_dir = os.path.dirname(rel_norm)
        title = _title_from_rel(rel_dir)

        try:
            raw = _read_text(fp)
        except Exception:
            continue

        cves = _extract_cves(rel_norm + "\n" + raw)
        sanitized, redacted_blocks = sanitize_markdown(raw)

        out_rel_dir = rel_dir
        out_dir = os.path.join(dest_root, out_rel_dir)
        out_name = os.path.basename(fp)
        out_path = os.path.join(out_dir, out_name)

        if (not args.overwrite) and os.path.exists(out_path):
            continue

        header = []
        header.append(f"# {title}")
        header.append("")
        header.append(f"- 来源: {fp}")
        header.append(f"- Vulhub 相对路径: {rel_norm}")
        if cves:
            header.append(f"- CVE: {', '.join(cves)}")
        header.append(f"- 脱敏代码块: {redacted_blocks}")
        header.append("")
        header.append("---")
        header.append("")
        content = "\n".join(header) + sanitized

        _write_file(out_path, content)
        entries.append(
            {
                "title": title,
                "rel": rel_norm,
                "out": os.path.relpath(out_path, base_dir).replace("\\", "/"),
                "cves": cves,
                "redacted_blocks": redacted_blocks,
            }
        )
        imported += 1

    entries.sort(key=lambda x: (x["out"], x["rel"]))

    idx_lines = []
    idx_lines.append("# Vulhub README 索引")
    idx_lines.append("")
    idx_lines.append(f"- 源目录: `{src_root}`")
    idx_lines.append(f"- 导入目录: `{args.dest}`")
    idx_lines.append(f"- 导入数量: {imported}")
    idx_lines.append("")
    idx_lines.append("## 条目列表")
    for e in entries:
        cve_part = f"（CVE: {', '.join(e['cves'])}）" if e["cves"] else ""
        idx_lines.append(f"- {e['title']} {cve_part} -> `{e['out']}`")
    idx_lines.append("")

    _write_file(index_path, "\n".join(idx_lines).rstrip() + "\n")
    print(f"imported={imported}")


if __name__ == "__main__":
    main()
