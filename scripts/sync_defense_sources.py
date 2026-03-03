import os
import subprocess
import sys
from typing import Any, Dict, List

import yaml


def _run(cmd: List[str], cwd: str | None = None) -> int:
    p = subprocess.run(cmd, cwd=cwd)
    return int(p.returncode)


def _git_exists() -> bool:
    try:
        p = subprocess.run(["git", "--version"], capture_output=True, text=True)
        return p.returncode == 0
    except Exception:
        return False


def _load_sources(config_path: str) -> List[Dict[str, Any]]:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sources = cfg.get("sources") or []
    if not isinstance(sources, list):
        return []
    return [s for s in sources if isinstance(s, dict)]


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "defense_sources.yaml")
    if not os.path.exists(config_path):
        print(f"缺少配置文件: {config_path}")
        sys.exit(1)

    if not _git_exists():
        print("未检测到 git，请先安装 git 后重试。")
        sys.exit(1)

    sources = _load_sources(config_path)
    if not sources:
        print("sources 为空，跳过。")
        sys.exit(0)

    failures = 0
    for s in sources:
        name = (s.get("name") or "").strip()
        url = (s.get("url") or "").strip()
        target_dir = (s.get("target_dir") or "").strip()
        if not name or not url or not target_dir:
            failures += 1
            continue

        abs_target = os.path.join(base_dir, target_dir)
        parent = os.path.dirname(abs_target)
        os.makedirs(parent, exist_ok=True)

        if not os.path.exists(abs_target):
            print(f"[clone] {name} -> {target_dir}")
            rc = _run(["git", "clone", "--depth", "1", url, abs_target])
        else:
            print(f"[pull]  {name} -> {target_dir}")
            rc = _run(["git", "pull", "--ff-only"], cwd=abs_target)

        if rc != 0:
            failures += 1
            print(f"[failed] {name} rc={rc}")

    if failures:
        print(f"完成：存在 {failures} 个失败源。")
        sys.exit(2)
    print("完成：全部同步成功。")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()

