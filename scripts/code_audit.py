import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    match: str
    message: str
    remediation: str


_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _iter_files(root: str) -> Iterable[str]:
    root = os.path.abspath(root)
    if os.path.isfile(root):
        yield root
        return

    skip_dir_names = {
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        "dist",
        "build",
    }
    skip_path_prefixes = {
        "data/vector_db",
        "data/models",
    }

    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        rel_posix = rel.replace("\\", "/")
        if rel_posix == ".":
            rel_posix = ""
        rel_posix_l = rel_posix.lower()

        if any(rel_posix_l.startswith(p) for p in skip_path_prefixes):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in skip_dir_names]

        for fn in filenames:
            if fn.endswith((".pyc", ".pyo")):
                continue
            yield os.path.join(dirpath, fn)


def _looks_text(path: str, max_bytes: int = 4096) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_bytes)
        if b"\x00" in chunk:
            return False
        return True
    except Exception:
        return False


def _read_lines(path: str, max_chars: int = 2_000_000) -> List[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        s = f.read(max_chars + 1)
    if len(s) > max_chars:
        s = s[:max_chars]
    return s.splitlines()


def _compile_rules() -> List[Tuple[str, str, re.Pattern, str, str]]:
    rules: List[Tuple[str, str, re.Pattern, str, str]] = []

    def add(rule_id: str, severity: str, pattern: str, message: str, remediation: str):
        rules.append((rule_id, severity, re.compile(pattern), message, remediation))

    add(
        "SECRET.AWS_ACCESS_KEY",
        "high",
        r"\bAKIA[0-9A-Z]{16}\b",
        "疑似 AWS Access Key 泄露。",
        "立即吊销/轮换密钥；将敏感配置迁移到环境变量/密钥管理系统，并加入泄露检测。",
    )
    add(
        "SECRET.OPENAI_LIKE_KEY",
        "high",
        r"\bsk-[A-Za-z0-9]{16,}\b",
        "疑似 API Key 泄露（sk- 前缀）。",
        "立即轮换 Key；避免写入仓库与日志；使用环境变量或密钥管理系统。",
    )
    add(
        "SECRET.PRIVATE_KEY_BLOCK",
        "critical",
        r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----",
        "发现私钥内容块。",
        "立即吊销/轮换相关密钥；删除仓库中的私钥；使用专用密钥管理并限制访问。",
    )
    add(
        "PY.SUBPROCESS_SHELL_TRUE",
        "high",
        r"\bsubprocess\.(?:run|Popen|call|check_output)\([^)]*shell\s*=\s*True",
        "subprocess 使用 shell=True，存在命令注入风险（取决于入参是否可控）。",
        "优先使用参数数组形式；对可控输入做严格白名单校验；避免拼接命令字符串。",
    )
    add(
        "PY.OS_SYSTEM",
        "high",
        r"\bos\.system\(",
        "使用 os.system 可能导致命令注入与可控参数风险。",
        "改用 subprocess 且使用参数数组；避免拼接；对可控输入做白名单校验。",
    )
    add(
        "PY.EVAL_EXEC",
        "high",
        r"\b(eval|exec)\(",
        "使用 eval/exec 可能导致代码注入（取决于入参是否可控）。",
        "避免对不可信输入使用 eval/exec；使用安全解析器或显式映射表。",
    )
    add(
        "PY.REQUESTS_VERIFY_FALSE",
        "medium",
        r"\bverify\s*=\s*False\b",
        "禁用 TLS 证书校验会导致中间人攻击风险。",
        "启用证书校验；必要时配置受信 CA 或 pinning。",
    )
    add(
        "JS.EVAL",
        "high",
        r"\beval\(",
        "使用 JavaScript eval 可能导致代码注入。",
        "避免 eval；使用安全的解析/映射方案。",
    )
    add(
        "JS.INNERHTML",
        "medium",
        r"\.innerHTML\s*=",
        "设置 innerHTML 可能引入 XSS（取决于数据是否可控）。",
        "对可控数据做严格转义/消毒；优先使用 textContent 或安全模板。",
    )
    return rules


def _scan_file(path: str, root: str, rules) -> List[Finding]:
    findings: List[Finding] = []
    if not _looks_text(path):
        return findings
    try:
        lines = _read_lines(path)
    except Exception:
        return findings

    rel_path = os.path.relpath(os.path.abspath(path), os.path.abspath(root))

    for i, line in enumerate(lines, start=1):
        for rule_id, severity, pat, msg, fix in rules:
            m = pat.search(line)
            if not m:
                continue
            findings.append(
                Finding(
                    rule_id=rule_id,
                    severity=severity,
                    file=rel_path.replace("\\", "/"),
                    line=i,
                    match=m.group(0)[:200],
                    message=msg,
                    remediation=fix,
                )
            )
    return findings


def _filter_findings(findings: List[Finding], min_severity: str) -> List[Finding]:
    threshold = _SEVERITY_ORDER.get(min_severity, 0)
    out = []
    for f in findings:
        if _SEVERITY_ORDER.get(f.severity, 0) >= threshold:
            out.append(f)
    return out


def _to_markdown(findings: List[Finding]) -> str:
    counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    lines = []
    lines.append("# 代码审计报告（快速规则扫描）")
    lines.append("")
    lines.append("## 概览")
    lines.append(f"- Critical: {counts.get('critical', 0)}")
    lines.append(f"- High: {counts.get('high', 0)}")
    lines.append(f"- Medium: {counts.get('medium', 0)}")
    lines.append(f"- Low: {counts.get('low', 0)}")
    lines.append("")

    if not findings:
        lines.append("未发现匹配规则的风险点。")
        return "\n".join(lines)

    lines.append("## 发现列表")
    for f in findings:
        lines.append(f"### {f.severity.upper()} {f.rule_id}")
        lines.append(f"- 位置: `{f.file}:{f.line}`")
        lines.append(f"- 命中: `{f.match}`")
        lines.append(f"- 说明: {f.message}")
        lines.append(f"- 建议: {f.remediation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="要审计的目录或文件路径")
    ap.add_argument("--min-severity", default="low", choices=["low", "medium", "high", "critical"])
    ap.add_argument("--format", default="md", choices=["md", "json"])
    ap.add_argument("--max-findings", type=int, default=3000)
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    rules = _compile_rules()

    findings: List[Finding] = []
    for fp in _iter_files(root):
        findings.extend(_scan_file(fp, root if os.path.isdir(root) else os.path.dirname(root), rules))
        if len(findings) >= args.max_findings:
            break

    findings = _filter_findings(findings, args.min_severity)
    findings.sort(key=lambda x: (-_SEVERITY_ORDER.get(x.severity, 0), x.file, x.line, x.rule_id))

    if args.format == "json":
        out = [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "match": f.match,
                "message": f.message,
                "remediation": f.remediation,
            }
            for f in findings
        ]
        print(json.dumps({"findings": out}, ensure_ascii=False, indent=2))
    else:
        print(_to_markdown(findings))


if __name__ == "__main__":
    main()
