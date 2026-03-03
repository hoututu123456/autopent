import os
import re
from typing import Dict, List, Optional, Tuple


_ALLOWED_EXTS = {".md", ".txt", ".yml", ".yaml", ".json"}


def _safe_join_under(base_dir: str, rel_path: str) -> Optional[str]:
    if not rel_path:
        return None
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    if ".." in rel_path:
        return None
    base_abs = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(base_abs, rel_path))
    if not (candidate == base_abs or candidate.startswith(base_abs + os.sep)):
        return None
    return candidate


class DefenseSearcher:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.defense_root = os.path.join(base_dir, "data", "external", "defense")

    def list_repos(self) -> List[Dict[str, str]]:
        root = self.defense_root
        if not os.path.exists(root):
            return []
        repos: List[Dict[str, str]] = []
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if os.path.isdir(p):
                repos.append({"name": name, "path": os.path.relpath(p, self.base_dir).replace("\\", "/")})
        return repos

    def read_file(self, rel_path: str, max_chars: int = 20000) -> Tuple[Optional[str], Optional[str]]:
        max_chars = max(100, min(int(max_chars), 200000))
        abs_path = _safe_join_under(self.base_dir, rel_path)
        if not abs_path:
            return None, "Invalid path"
        if not abs_path.startswith(os.path.abspath(self.defense_root) + os.sep):
            return None, "Forbidden"
        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            return None, "Not found"

        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in _ALLOWED_EXTS:
            return None, "Unsupported file type"

        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(max_chars + 1)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[内容已截断]..."
        return text, None

    def search(self, query: str, limit: int = 30) -> List[Dict[str, str]]:
        q = (query or "").strip()
        if not q:
            return []
        limit = max(1, min(int(limit), 200))
        root = self.defense_root
        if not os.path.exists(root):
            return []

        needle = q.lower()
        results: List[Dict[str, str]] = []
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if len(results) >= limit:
                    return results
                ext = os.path.splitext(fn)[1].lower()
                if ext not in _ALLOWED_EXTS:
                    continue
                abs_path = os.path.join(dirpath, fn)
                rel = os.path.relpath(abs_path, self.base_dir).replace("\\", "/")
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        chunk = f.read(50000)
                except Exception:
                    continue

                hay = chunk.lower()
                if needle in fn.lower() or needle in hay:
                    idx = hay.find(needle)
                    snippet = ""
                    if idx >= 0:
                        start = max(0, idx - 120)
                        end = min(len(chunk), idx + 240)
                        snippet = chunk[start:end].replace("\n", " ").strip()
                    results.append({"path": rel, "snippet": snippet})
        return results


_TTP_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)


def extract_ttps(text: str) -> List[str]:
    if not text:
        return []
    seen = set()
    out: List[str] = []
    for m in _TTP_RE.finditer(text):
        v = m.group(0).upper()
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out[:50]


def extract_cves(text: str) -> List[str]:
    if not text:
        return []
    seen = set()
    out: List[str] = []
    for m in _CVE_RE.finditer(text):
        v = m.group(0).upper()
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out[:50]

