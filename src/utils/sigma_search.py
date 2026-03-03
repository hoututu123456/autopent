import os
from typing import Dict, List


_ALLOWED_EXTS = {".yml", ".yaml", ".md", ".txt"}


class SigmaSearcher:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.root = os.path.join(base_dir, "data", "external", "defense", "sigma")

    def available(self) -> bool:
        return os.path.exists(self.root) and os.path.isdir(self.root)

    def search(self, query: str, limit: int = 30) -> List[Dict[str, str]]:
        q = (query or "").strip().lower()
        if not q or not self.available():
            return []
        limit = max(1, min(int(limit), 200))
        results: List[Dict[str, str]] = []

        rules_root = os.path.join(self.root, "rules")
        walk_root = rules_root if os.path.exists(rules_root) else self.root

        for dirpath, _, filenames in os.walk(walk_root):
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
                        chunk = f.read(60000)
                except Exception:
                    continue
                hay = (fn + "\n" + chunk).lower()
                if q in hay:
                    idx = hay.find(q)
                    snippet = ""
                    if idx >= 0:
                        start = max(0, idx - 120)
                        end = min(len(chunk), idx + 240)
                        snippet = chunk[start:end].replace("\n", " ").strip()
                    results.append({"path": rel, "snippet": snippet})
        return results

