import argparse
import glob
import json
import os
import shlex
import shutil
from typing import Dict, List, Optional, Tuple


def _strip_quotes(s: str) -> str:
    v = (s or "").strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1].strip()
    return v


def _parse_yaml_minimal(path: str) -> Tuple[str, str, bool]:
    name = ""
    command = ""
    enabled = True
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("name:") and not name:
                    name = _strip_quotes(line.split(":", 1)[1].strip())
                    continue
                if (line.startswith("command:") or line.startswith("binary:")) and not command:
                    command = _strip_quotes(line.split(":", 1)[1].strip())
                    continue
                if line.startswith("enabled:"):
                    v = line.split(":", 1)[1].strip().lower()
                    enabled = v not in {"false", "0", "no"}
    except Exception:
        return name, command, enabled
    return name, command, enabled


def _extract_executable(command: str) -> Optional[str]:
    c = (command or "").strip()
    if not c:
        return None
    try:
        parts = shlex.split(c)
    except Exception:
        parts = c.split()
    if not parts:
        return None
    exe = parts[0]
    return exe


def _is_present(exe: str) -> bool:
    if not exe:
        return False
    if exe.startswith("/") or exe.startswith("\\") or (len(exe) > 2 and exe[1] == ":" and (exe[2] in {"\\", "/"})):
        return os.path.exists(exe)
    return shutil.which(exe) is not None


def _pkg_manager() -> str:
    if shutil.which("apt-get"):
        return "apt"
    if shutil.which("dnf"):
        return "dnf"
    if shutil.which("yum"):
        return "yum"
    return "unknown"


def _map_exec_to_pkg(exec_name: str, pm: str) -> Optional[str]:
    e = (exec_name or "").strip()
    if not e:
        return None
    if pm == "apt":
        mapping = {
            "msfconsole": "metasploit-framework",
            "searchsploit": "exploitdb",
            "strings": "binutils",
            "rpcclient": "samba-common-bin",
            "enum4linux-ng": "enum4linux-ng",
            "enum4linux": "enum4linux",
            "smbmap": "smbmap",
            "nbtscan": "nbtscan",
            "responder": "responder",
            "netexec": "netexec",
            "ncat": "ncat",
            "ssh": "openssh-client",
            "chromium": "chromium",
        }
        return mapping.get(e)
    if pm in {"dnf", "yum"}:
        mapping = {
            "rpcclient": "samba-client",
            "ssh": "openssh-clients",
            "ncat": "nmap-ncat",
        }
        return mapping.get(e)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools-dir", default=os.path.join("config", "tools"))
    ap.add_argument("--pm", default="auto", choices=["auto", "apt", "dnf", "yum", "unknown"])
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--print-packages", action="store_true")
    args = ap.parse_args()

    pm = args.pm
    if pm == "auto":
        pm = _pkg_manager()

    tools_dir = os.path.abspath(args.tools_dir)
    yamls = glob.glob(os.path.join(tools_dir, "*.yaml"))
    ignore_execs = {
        "python",
        "python3",
        "/bin/bash",
        "bash",
        "sh",
        "pwsh",
        "powershell",
        "cmd.exe",
    }

    missing: List[Dict] = []
    missing_execs: Dict[str, int] = {}
    for y in yamls:
        name, command, enabled = _parse_yaml_minimal(y)
        if not enabled:
            continue
        exe = _extract_executable(command)
        if not exe:
            continue
        if exe in ignore_execs:
            continue
        if _is_present(exe):
            continue
        missing.append({"tool": name or os.path.basename(y), "exec": exe, "yaml": os.path.basename(y)})
        missing_execs[exe] = missing_execs.get(exe, 0) + 1

    pkgs = []
    for exe in sorted(missing_execs.keys()):
        p = _map_exec_to_pkg(exe, pm)
        if p and p not in pkgs:
            pkgs.append(p)

    report = {
        "pm": pm,
        "tools_dir": tools_dir,
        "yaml_count": len(yamls),
        "missing_exec_count": len(missing_execs),
        "missing_tools_count": len(missing),
        "missing": missing[:200],
        "suggested_packages": pkgs,
    }

    if args.print_packages:
        print(" ".join(pkgs))
        if args.strict and missing_execs:
            return 1
        return 0

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[tool_catalog] yaml_count={len(yamls)} missing_execs={len(missing_execs)} missing_tools={len(missing)}")
        if pkgs:
            print(f"[tool_catalog] suggested_packages ({pm}): " + " ".join(pkgs))
        if missing:
            for it in missing[:50]:
                print(f"- missing exec={it['exec']} (tool={it['tool']}, yaml={it['yaml']})")
            if len(missing) > 50:
                print(f"... truncated ({len(missing) - 50} more)")

    if args.strict and missing_execs:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
