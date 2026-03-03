import json
import os
import re
from typing import Any, Dict, List, Optional


_TTP_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)


class MitreAttack:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._loaded = False
        self._techniques: List[Dict[str, Any]] = []

    def _find_enterprise_attack_json(self) -> Optional[str]:
        root = os.path.join(self.base_dir, "data", "external", "defense")
        candidates = [
            os.path.join(root, "attack-stix-data", "enterprise-attack", "enterprise-attack.json"),
            os.path.join(root, "attack-stix-data", "enterprise-attack.json"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn == "enterprise-attack.json":
                    p = os.path.join(dirpath, fn)
                    if os.path.exists(p):
                        return p
        return None

    def load(self) -> bool:
        if self._loaded:
            return True
        path = self._find_enterprise_attack_json()
        if not path:
            self._loaded = True
            self._techniques = []
            return False
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except Exception:
            self._loaded = True
            self._techniques = []
            return False

        objs = data.get("objects") if isinstance(data, dict) else None
        if not isinstance(objs, list):
            self._loaded = True
            self._techniques = []
            return False

        techniques: List[Dict[str, Any]] = []
        for o in objs:
            if not isinstance(o, dict):
                continue
            if o.get("type") != "attack-pattern":
                continue
            name = o.get("name") or ""
            desc = o.get("description") or ""
            ext_refs = o.get("external_references") or []
            tid = None
            url = None
            if isinstance(ext_refs, list):
                for r in ext_refs:
                    if not isinstance(r, dict):
                        continue
                    if r.get("source_name") == "mitre-attack" and r.get("external_id"):
                        tid = str(r.get("external_id")).upper()
                        url = r.get("url") or url
                        break
            if tid:
                techniques.append(
                    {
                        "id": tid,
                        "name": name,
                        "url": url or "",
                        "description": desc[:1200],
                    }
                )

        self._techniques = techniques
        self._loaded = True
        return True

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        self.load()
        q = (query or "").strip()
        if not q:
            return []
        limit = max(1, min(int(limit), 200))
        ql = q.lower()
        matches: List[Dict[str, Any]] = []
        for t in self._techniques:
            if len(matches) >= limit:
                break
            if ql in (t.get("id") or "").lower() or ql in (t.get("name") or "").lower() or ql in (t.get("description") or "").lower():
                matches.append(t)
        return matches

    def extract_ids(self, text: str) -> List[str]:
        if not text:
            return []
        seen = set()
        out: List[str] = []
        for m in _TTP_RE.finditer(text):
            tid = m.group(0).upper()
            if tid not in seen:
                seen.add(tid)
                out.append(tid)
        return out[:50]

