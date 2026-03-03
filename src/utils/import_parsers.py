import csv
import io
import re
from typing import Dict, List, Tuple


_UNAUTH_MARKERS = ("unauthorized", "unauth", "no auth", "未授权", "未授权访问", "匿名登录")


def _normalize_service_type(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return ""
    lower = t.lower()
    type_map = {
        "redis": "Redis",
        "mysql": "MySQL",
        "mssql": "SQLServer",
        "sqlserver": "SQLServer",
        "oracle": "Oracle",
        "postgres": "PostgreSQL",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "mongo": "MongoDB",
        "ssh": "SSH",
        "ftp": "FTP",
        "sftp": "SFTP",
        "smb": "SMB",
        "rdp": "RDP",
        "wmi": "WMI",
        "memcached": "Memcached",
        "elasticsearch": "Elasticsearch",
        "es": "Elasticsearch",
        "rabbitmq": "RabbitMQ",
        "mqtt": "MQTT",
        "zookeeper": "Zookeeper",
        "etcd": "Etcd",
        "kafka": "Kafka",
        "vnc": "VNC",
        "adb": "ADB",
        "jdwp": "JDWP",
        "rmi": "RMI",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "k8s": "Kubernetes",
    }
    if lower in type_map:
        return type_map[lower]
    return t[:1].upper() + t[1:]


def _is_unauthorized(text: str) -> bool:
    h = (text or "").lower()
    return any(m in h for m in _UNAUTH_MARKERS)


def _mask_secret(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    if len(s) <= 2:
        return "*" * len(s)
    return s[:1] + ("*" * (len(s) - 2)) + s[-1:]


def _dedupe(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        k = (
            it.get("service_type", ""),
            it.get("ip", ""),
            it.get("port", ""),
            it.get("username", ""),
            it.get("password_masked", ""),
            it.get("finding_type", ""),
        )
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def parse_fscan_184(content: str) -> List[Dict]:
    lines = (content or "").splitlines()
    results: List[Dict] = []
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("[+]"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        service_info = parts[1]
        segs = service_info.split(":")
        if len(segs) < 3:
            continue
        service_type = _normalize_service_type(segs[0].strip())
        ip = segs[1].strip()
        port = segs[2].strip()
        cred_info = " ".join(parts[2:]).strip() if len(parts) >= 3 else ""

        username = ""
        password = ""
        finding_type = "unknown"
        if _is_unauthorized(cred_info):
            finding_type = "unauthorized"
        else:
            finding_type = "weak_credential" if cred_info else "exposed_service"
            if ":" in cred_info:
                u, p = cred_info.split(":", 1)
                username = u.strip()
                password = p.strip()
            else:
                username = cred_info.strip()

        results.append(
            {
                "source": "fscan-1.8.4",
                "service_type": service_type,
                "ip": ip,
                "port": port,
                "finding_type": finding_type,
                "username": username,
                "password_masked": _mask_secret(password),
                "raw": line[:500],
            }
        )
    return _dedupe(results)


def parse_fscan_211(content: str) -> List[Dict]:
    lines = (content or "").splitlines()
    results: List[Dict] = []
    in_vuln = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "# =====" in line and "漏洞信息" in line:
            in_vuln = True
            continue
        if line.startswith("# =====") and "漏洞信息" not in line:
            in_vuln = False
            continue
        if not in_vuln or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue
        ip_port = parts[0]
        if ":" not in ip_port:
            continue
        ip, port = ip_port.split(":", 1)
        service_type = _normalize_service_type(parts[1])
        if not service_type:
            continue
        cred = parts[2] if len(parts) >= 3 else ""

        username = ""
        password = ""
        finding_type = "unknown"
        if _is_unauthorized(line) or cred.strip() == "/":
            finding_type = "unauthorized"
        elif cred:
            finding_type = "weak_credential"
            if "/" in cred:
                u, p = cred.split("/", 1)
                username = u.strip()
                password = p.strip()
            else:
                username = cred.strip()
        else:
            finding_type = "exposed_service"

        results.append(
            {
                "source": "fscan-2.1.1",
                "service_type": service_type,
                "ip": ip.strip(),
                "port": port.strip(),
                "finding_type": finding_type,
                "username": username,
                "password_masked": _mask_secret(password),
                "raw": line[:500],
            }
        )
    return _dedupe(results)


_LIGHTX_RE = re.compile(r"\[Plugin:(?P<svc>[^:\]]+):SUCCESS\]", re.IGNORECASE)


def parse_lightx(content: str) -> List[Dict]:
    lines = (content or "").splitlines()
    results: List[Dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = _LIGHTX_RE.search(line)
        if not m:
            continue
        svc = m.group("svc").strip()
        if svc == "NetInfo":
            continue

        tail = line[m.end() :].strip()
        parts = tail.split()
        if len(parts) < 1:
            continue
        service_info = parts[0]
        segs = service_info.split(":")
        if len(segs) < 3:
            continue
        service_type = _normalize_service_type(segs[0].strip())
        ip = segs[1].strip()
        port = segs[2].strip()

        username = ""
        password = ""
        finding_type = "unknown"
        if _is_unauthorized(line):
            finding_type = "unauthorized"
            if len(parts) >= 2 and "anonymous" in parts[1].lower():
                username = "anonymous"
        else:
            if len(parts) >= 2:
                cred = parts[1]
                finding_type = "weak_credential"
                if "/" in cred:
                    u, p = cred.split("/", 1)
                    username = u.strip()
                    password = p.strip()
            else:
                finding_type = "exposed_service"

        results.append(
            {
                "source": "lightx",
                "service_type": service_type,
                "ip": ip,
                "port": port,
                "finding_type": finding_type,
                "username": username,
                "password_masked": _mask_secret(password),
                "raw": line[:500],
            }
        )
    return _dedupe(results)


def parse_csv_generic(content: str) -> List[Dict]:
    s = content or ""
    reader = csv.DictReader(io.StringIO(s))
    results: List[Dict] = []
    for row in reader:
        if not isinstance(row, dict):
            continue
        ip = (row.get("ip") or row.get("IP") or row.get("host") or row.get("Host") or "").strip()
        port = (row.get("port") or row.get("Port") or "").strip()
        service = (row.get("type") or row.get("Type") or row.get("service") or row.get("Service") or "").strip()
        user = (row.get("user") or row.get("User") or row.get("username") or "").strip()
        password = (row.get("pass") or row.get("Pass") or row.get("password") or "").strip()
        msg = (row.get("message") or row.get("Message") or row.get("result") or row.get("Result") or "").strip()

        if not ip or not port or not service:
            continue

        service_type = _normalize_service_type(service)
        finding_type = "weak_credential" if (user or password) else ("unauthorized" if _is_unauthorized(msg) else "exposed_service")

        results.append(
            {
                "source": "csv",
                "service_type": service_type,
                "ip": ip,
                "port": port,
                "finding_type": finding_type,
                "username": user,
                "password_masked": _mask_secret(password),
                "raw": msg[:500],
            }
        )
    return _dedupe(results)


def detect_and_parse(content: str, filename: str = "") -> Tuple[str, List[Dict]]:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return "csv", parse_csv_generic(content)
    if "[Plugin:" in (content or "") and ":SUCCESS]" in (content or ""):
        return "lightx", parse_lightx(content)
    if "# ===== 漏洞信息 =====" in (content or ""):
        return "fscan-2.1.1", parse_fscan_211(content)
    if "[+]" in (content or ""):
        return "fscan-1.8.4", parse_fscan_184(content)
    return "unknown", []

