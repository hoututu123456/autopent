import os
import shutil
import sys


REQUIRED_TOOLS = [
    "nmap",
    "sqlmap",
    "gobuster",
    "curl",
    "hydra",
    "dirsearch",
    "nuclei",
    "subfinder",
    "ssh",
    "ncat",
    "searchsploit",
]
OPTIONAL_TOOLS = [
    "msfconsole",
    "dirb",
    "nikto",
    "feroxbuster",
    "wpscan",
    "hashcat",
    "john",
    "enum4linux-ng",
    "enum4linux",
    "smbmap",
    "rpcclient",
    "nbtscan",
    "responder",
    "netexec",
    "volatility",
    "radare2",
    "binwalk",
    "strings",
]

BROWSER_CANDIDATES = [
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "firefox",
    "firefox-esr",
]


def _detect_pkg_manager():
    if shutil.which("apt-get"):
        return "apt"
    if shutil.which("dnf"):
        return "dnf"
    if shutil.which("yum"):
        return "yum"
    return None


def _install_hint(missing):
    pm = _detect_pkg_manager()
    if pm == "apt":
        return f"sudo apt update && sudo apt install {' '.join(missing)} -y"
    if pm == "dnf":
        return f"sudo dnf install {' '.join(missing)} -y"
    if pm == "yum":
        return f"sudo yum install {' '.join(missing)} -y"
    return "请使用系统包管理器安装缺失工具，或使用项目的一键脚本 run.sh / run-linux.sh"


def check_dependencies():
    print("Checking system dependencies...")
    missing_tools = []
    missing_python = []

    if sys.version_info < (3, 10):
        print("Python 3.10+ is required.")
        return False
    print("✅ Python Version OK")

    try:
        import duckduckgo_search  # noqa: F401

        print("✅ Found python library: duckduckgo-search")
    except ImportError:
        print("⚠️  Optional python library 'duckduckgo-search' not found. Self-learning might be limited.")

    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import pydantic  # noqa: F401
        import yaml  # noqa: F401
        import httpx  # noqa: F401
        import sse_starlette  # noqa: F401
        import jinja2  # noqa: F401
        import dotenv  # noqa: F401
        import openai  # noqa: F401
        import multipart  # noqa: F401

        print("✅ Found core python libraries (FastAPI runtime ready)")
    except ImportError:
        missing_python.append("fastapi/uvicorn/pydantic/pyyaml/httpx/sse-starlette/jinja2/python-dotenv/openai/python-multipart")

    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        print("✅ Found RAG dependencies (chromadb & sentence-transformers)")
    except ImportError:
        print("⚠️  Missing RAG dependencies (chromadb, sentence-transformers). Semantic search will be degraded.")

    try:
        import psutil  # noqa: F401
        print("✅ Found python library: psutil (system metrics ready)")
    except ImportError:
        print("⚠️  Optional python library 'psutil' not found. System performance monitor will be degraded.")

    for tool in REQUIRED_TOOLS:
        path = shutil.which(tool)
        if path:
            print(f"✅ Found {tool}: {path}")
        else:
            print(f"❌ Missing {tool}.")
            missing_tools.append(tool)

    for tool in OPTIONAL_TOOLS:
        path = shutil.which(tool)
        if path:
            print(f"✅ Found optional {tool}: {path}")
        else:
            print(f"⚠️  Optional {tool} not found.")

    browser = None
    for b in BROWSER_CANDIDATES:
        if shutil.which(b):
            browser = b
            break
    if browser:
        print(f"✅ Found browser for screenshots: {browser}")
    else:
        print("❌ Missing headless-capable browser (chromium/chrome/firefox). Screenshots will fail.")
        missing_tools.append("chromium")

    strict = os.getenv("STRICT_DEPS", "").strip() in {"1", "true", "yes"}
    if missing_python:
        print("\nCRITICAL: Missing core python dependencies.")
        print("Please run: pip install -r requirements.txt")
        return False

    if missing_tools:
        print("\nWARNING: Some recommended tools are missing.")
        print(_install_hint([m for m in missing_tools if m]))
        if strict:
            return False

    print("\nAll systems go! Ready to launch.")
    return True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not check_dependencies():
        sys.exit(1)
