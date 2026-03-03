import argparse
import hashlib
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple


def _sha256(path: str, max_bytes: Optional[int] = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            if max_bytes is not None and f.tell() >= max_bytes:
                break
    return h.hexdigest()


def _run(cmd: List[str], timeout_s: int = 30, max_chars: int = 40000) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, errors="replace")
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
        if len(out) > max_chars:
            out = out[:max_chars] + "\n...[输出已截断]..."
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return -2, "[timeout] 命令执行超时"
    except Exception as e:
        return -1, f"[error] {e}"


def _tool(name: str) -> Optional[str]:
    return shutil.which(name)


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.rstrip()}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="要分析的二进制/样本文件路径")
    ap.add_argument("--strings-min-len", type=int, default=4)
    ap.add_argument("--max-strings-lines", type=int, default=200)
    args = ap.parse_args()

    fp = os.path.abspath(args.file)
    if not os.path.exists(fp) or not os.path.isfile(fp):
        raise SystemExit("file_not_found")

    st = os.stat(fp)
    sha = _sha256(fp)

    lines: List[str] = []
    lines.append("# 二进制快速体检报告（Triage）")
    lines.append("")
    lines.append(_section("基本信息", f"- 路径: `{fp}`\n- 大小: {st.st_size} bytes\n- SHA256: `{sha}`"))

    file_cmd = _tool("file")
    if file_cmd:
        rc, out = _run([file_cmd, "-b", fp], timeout_s=10, max_chars=8000)
        lines.append(_section("file(1) 识别", f"返回码: {rc}\n\n```\n{out}\n```"))
    else:
        lines.append(_section("file(1) 识别", "未找到 `file` 命令，跳过。"))

    checksec_cmd = _tool("checksec")
    if checksec_cmd:
        rc, out = _run([checksec_cmd, "--file=" + fp], timeout_s=15, max_chars=20000)
        lines.append(_section("checksec", f"返回码: {rc}\n\n```\n{out}\n```"))
    else:
        lines.append(_section("checksec", "未找到 `checksec` 命令，跳过。"))

    objdump_cmd = _tool("objdump")
    if objdump_cmd:
        rc1, out1 = _run([objdump_cmd, "-f", fp], timeout_s=15, max_chars=20000)
        rc2, out2 = _run([objdump_cmd, "-h", fp], timeout_s=15, max_chars=20000)
        body = f"### objdump -f\n返回码: {rc1}\n\n```\n{out1}\n```\n\n### objdump -h\n返回码: {rc2}\n\n```\n{out2}\n```"
        lines.append(_section("objdump", body))
    else:
        lines.append(_section("objdump", "未找到 `objdump` 命令，跳过。"))

    strings_cmd = _tool("strings")
    if strings_cmd:
        rc, out = _run([strings_cmd, "-n", str(max(1, args.strings_min_len)), fp], timeout_s=20, max_chars=200000)
        out_lines = out.splitlines()
        out_preview = "\n".join(out_lines[: max(1, args.max_strings_lines)])
        lines.append(_section("strings（节选）", f"返回码: {rc}\n\n```\n{out_preview}\n```"))
    else:
        lines.append(_section("strings", "未找到 `strings` 命令，跳过。"))

    binwalk_cmd = _tool("binwalk")
    if binwalk_cmd:
        rc, out = _run([binwalk_cmd, "--signature", fp], timeout_s=30, max_chars=40000)
        lines.append(_section("binwalk --signature", f"返回码: {rc}\n\n```\n{out}\n```"))
    else:
        lines.append(_section("binwalk", "未找到 `binwalk` 命令，跳过。"))

    exif_cmd = _tool("exiftool")
    if exif_cmd:
        rc, out = _run([exif_cmd, fp], timeout_s=20, max_chars=30000)
        lines.append(_section("exiftool", f"返回码: {rc}\n\n```\n{out}\n```"))
    else:
        lines.append(_section("exiftool", "未找到 `exiftool` 命令，跳过。"))

    print("\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    main()

