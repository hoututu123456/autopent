import argparse
import json
import os
from typing import Dict, List, Optional


def _extract_url_and_title(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = []
            for _ in range(40):
                ln = f.readline()
                if not ln:
                    break
                head.append(ln)
    except Exception:
        return None

    title = ""
    url = ""
    for ln in head:
        s = ln.strip()
        if not title and s.startswith("# "):
            title = s[2:].strip()
        if s.startswith("- 来源:"):
            url = s.split(":", 1)[1].strip()
    if not url:
        return None
    return {"url": url, "title": title}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default="data/skills")
    ap.add_argument("--knowledge-dir", default="data/knowledge")
    ap.add_argument("--out", default="data/temp/crawl_index.json")
    args = ap.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    skills_dir = os.path.join(base_dir, args.skills_dir)
    kb_dir = os.path.join(base_dir, args.knowledge_dir)
    out_path = os.path.join(base_dir, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    targets = {
        "YakLab": {"target": "YakLab", "saved": []},
        "SSA": {"target": "SSA", "saved": []},
    }

    def add_from_dir(root: str, target_name: str, category: str):
        if not os.path.exists(root):
            return
        for fn in os.listdir(root):
            if not fn.endswith(".md"):
                continue
            if not fn.startswith(target_name + "_"):
                continue
            fp = os.path.join(root, fn)
            meta = _extract_url_and_title(fp)
            if not meta:
                continue
            targets[target_name]["saved"].append(
                {"url": meta["url"], "title": meta.get("title", ""), "category": category, "file": fp}
            )

    add_from_dir(skills_dir, "YakLab", "skills")
    add_from_dir(kb_dir, "YakLab", "knowledge")
    add_from_dir(skills_dir, "SSA", "skills")
    add_from_dir(kb_dir, "SSA", "knowledge")

    for t in targets.values():
        t["saved_count"] = len(t["saved"])

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)

    print(json.dumps({k: {"saved_count": v["saved_count"]} for k, v in targets.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
