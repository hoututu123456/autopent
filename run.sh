#!/bin/bash

# AutoPentestAI - Autonomous Security Platform (Kali Linux Launcher)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

set -euo pipefail

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}      AutoPentestAI - Autonomous Security Platform${NC}"
echo -e "${GREEN}==================================================${NC}"

APT_GET_OPTS=(-o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)
USE_GHPROXY="${USE_GHPROXY:-1}"
GHPROXY_PREFIX="${GHPROXY_PREFIX:-https://ghproxy.com/}"
PIP_INDEX_URL_DEFAULT="${PIP_INDEX_URL_DEFAULT:-https://pypi.tuna.tsinghua.edu.cn/simple}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cpu}"

read_env_kv() {
    local key="$1"
    local file="${2:-.env}"
    if [ ! -f "$file" ]; then
        return 0
    fi
    local line
    line="$(grep -E "^${key}=" "$file" 2>/dev/null | tail -n 1 || true)"
    if [ -z "$line" ]; then
        return 0
    fi
    echo "${line#*=}" | sed 's/^"//; s/"$//'
}

apply_proxy_from_env() {
    local proxy
    proxy="$(read_env_kv "PROXY_URL" ".env" || true)"
    proxy="$(echo -n "$proxy" | xargs || true)"
    if [ -n "${proxy:-}" ]; then
        export http_proxy="$proxy"
        export https_proxy="$proxy"
        export HTTP_PROXY="$proxy"
        export HTTPS_PROXY="$proxy"
        export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"
        export NO_PROXY="${NO_PROXY:-$no_proxy}"
        echo -e "${YELLOW}[INFO] Using proxy from .env (PROXY_URL) for downloads.${NC}"
    fi
}

curl_retry() {
    curl --retry 6 --retry-all-errors --retry-delay 2 --connect-timeout 10 --max-time 300 -fsSL "$@"
}

# 0. Base Packages (apt)
echo -e "${YELLOW}[INFO] Ensuring base packages...${NC}"
sudo apt-get "${APT_GET_OPTS[@]}" update
sudo apt-get "${APT_GET_OPTS[@]}" install -y ca-certificates curl wget git unzip tar jq python3 python3-venv python3-pip build-essential python3-dev

# 1. Environment Setup (.env)
if [ ! -f .env ]; then
    echo -e "${YELLOW}[INFO] .env file not found. Creating from example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}[SUCCESS] Created .env file.${NC}"
        echo -e "${YELLOW}[NOTE] You can set your DeepSeek API Key later in the Web UI Settings.${NC}"
    else
        # Create a default .env if example is missing
        {
            echo "AI_PROVIDER=deepseek"
            echo "AI_MODEL=deepseek-reasoner"
            echo "DEEPSEEK_API_KEY="
            echo "OPENAI_API_KEY="
            echo "DEEPSEEK_OCR_API_KEY="
            echo "DEEPSEEK_OCR_BASE_URL=https://api.deepseek.com/v1"
            echo "DEEPSEEK_OCR_MODEL=DeepSeek-OCR-2"
            echo "DEEPSEEK_OCR_TIMEOUT=120"
            echo "PROXY_URL="
            echo "AI_LHOST="
            echo "AI_BIND_INTERFACE=eth0"
        } > .env
        echo -e "${GREEN}[SUCCESS] Created new .env file.${NC}"
    fi
fi

# Ensure optional networking env keys exist (for reverse shells / multi-NIC setups)
if ! grep -q "^AI_LHOST=" .env 2>/dev/null; then
    echo "" >> .env
    echo "AI_LHOST=" >> .env
fi
default_iface="$(ip route show default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')"
if [ -z "$default_iface" ]; then
    default_iface="eth0"
fi
if ! grep -q "^AI_BIND_INTERFACE=" .env 2>/dev/null; then
    echo "AI_BIND_INTERFACE=$default_iface" >> .env
else
    current_iface="$(grep "^AI_BIND_INTERFACE=" .env | tail -n 1 | cut -d= -f2-)"
    if [ -z "$current_iface" ]; then
        sed -i "s/^AI_BIND_INTERFACE=.*/AI_BIND_INTERFACE=$default_iface/" .env
    fi
fi

if ! grep -q "^AI_PROVIDER=" .env 2>/dev/null; then
    echo "AI_PROVIDER=deepseek" >> .env
fi
if ! grep -q "^AI_MODEL=" .env 2>/dev/null; then
    echo "AI_MODEL=deepseek-reasoner" >> .env
fi
if ! grep -q "^OPENAI_API_KEY=" .env 2>/dev/null; then
    echo "OPENAI_API_KEY=" >> .env
fi
if ! grep -q "^PROXY_URL=" .env 2>/dev/null; then
    echo "PROXY_URL=" >> .env
fi

apply_proxy_from_env

# 2. System Dependencies (apt)
echo -e "${YELLOW}[INFO] Checking system tools...${NC}"
MISSING_TOOLS=()

REQUIRED_TOOLS=(
    "nmap" "sqlmap" "gobuster" "hydra" "dirsearch" "nuclei" "subfinder"
    "ssh" "ncat" "searchsploit"
)
OPTIONAL_TOOLS=(
    "dirb" "nikto" "feroxbuster" "wpscan" "hashcat" "john" "radare2" "binwalk" "strings"
    "enum4linux-ng" "enum4linux" "smbmap" "rpcclient" "nbtscan" "responder" "netexec"
)

BROWSER_CANDIDATES=(
    "chromium" "chromium-browser" "google-chrome" "google-chrome-stable" "firefox" "firefox-esr"
)

has_browser=0
for b in "${BROWSER_CANDIDATES[@]}"; do
    if command -v "$b" &> /dev/null; then
        has_browser=1
        break
    fi
done
if [ $has_browser -eq 0 ]; then
    MISSING_TOOLS+=("browser")
fi

for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS+=("$tool")
    fi
done
for tool in "${OPTIONAL_TOOLS[@]}"; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS+=("$tool")
    fi
done

if [ ${#MISSING_TOOLS[@]} -ne 0 ]; then
    echo -e "${YELLOW}[INFO] Missing tools found: ${MISSING_TOOLS[*]}${NC}"
    echo -e "${YELLOW}[INFO] Attempting to install missing tools (requires sudo)...${NC}"
    
    # Map tools to package names (some differ)
    PACKAGES=()
    for tool in "${MISSING_TOOLS[@]}"; do
        case "$tool" in
            "ncat") PACKAGES+=("ncat") ;;
            "searchsploit") PACKAGES+=("exploitdb") ;;
            "strings") PACKAGES+=("binutils") ;;
            "ssh") PACKAGES+=("openssh-client") ;;
            "rpcclient") PACKAGES+=("samba-common-bin") ;;
            "enum4linux-ng") PACKAGES+=("enum4linux-ng") ;;
            "enum4linux") PACKAGES+=("enum4linux") ;;
            "smbmap") PACKAGES+=("smbmap") ;;
            "nbtscan") PACKAGES+=("nbtscan") ;;
            "responder") PACKAGES+=("responder") ;;
            "netexec") PACKAGES+=("netexec") ;;
            "browser") PACKAGES+=("chromium") ;;
            *) PACKAGES+=("$tool") ;;
        esac
    done
    
    sudo apt-get "${APT_GET_OPTS[@]}" update
    FAILED_PKGS=()
    for pkg in "${PACKAGES[@]}"; do
        sudo apt-get "${APT_GET_OPTS[@]}" install -y "$pkg" || FAILED_PKGS+=("$pkg")
    done
    
    if [ ${#FAILED_PKGS[@]} -ne 0 ]; then
        echo -e "${YELLOW}[WARNING] Some packages failed to install: ${FAILED_PKGS[*]}${NC}"
        echo -e "${YELLOW}[TIP] You can install missing tools manually, or verify they exist in Kali repositories.${NC}"
    else
        echo -e "${GREEN}[SUCCESS] System tools installed.${NC}"
    fi
fi

# Fallback installers (Kali sometimes lacks latest packages)
github_latest_tag() {
    local repo="$1"
    local api_url="https://api.github.com/repos/$repo/releases/latest"
    local body=""
    body="$(curl_retry "$api_url" 2>/dev/null || true)"
    if [ -z "$body" ] && [ "$USE_GHPROXY" = "1" ]; then
        body="$(curl_retry "${GHPROXY_PREFIX}${api_url}" 2>/dev/null || true)"
    fi
    echo "$body" | sed -n 's/.*"tag_name":[ ]*"\([^"]*\)".*/\1/p' | head -n 1
}

install_zip_binary() {
    local url="$1"
    local bin_name="$2"
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    local zip_path="$tmp_dir/pkg.zip"
    if ! curl_retry "$url" -o "$zip_path"; then
        if [ "$USE_GHPROXY" = "1" ]; then
            curl_retry "${GHPROXY_PREFIX}${url}" -o "$zip_path" || { rm -rf "$tmp_dir"; return 1; }
        else
            rm -rf "$tmp_dir"
            return 1
        fi
    fi
    if ! unzip -q "$zip_path" -d "$tmp_dir"; then
        rm -rf "$tmp_dir"
        return 1
    fi
    if [ ! -f "$tmp_dir/$bin_name" ] && [ -f "$tmp_dir/$bin_name/$bin_name" ]; then
        mv "$tmp_dir/$bin_name/$bin_name" "$tmp_dir/$bin_name"
    fi
    if [ ! -f "$tmp_dir/$bin_name" ]; then
        rm -rf "$tmp_dir"
        return 1
    fi
    sudo install -m 0755 "$tmp_dir/$bin_name" /usr/local/bin/"$bin_name"
    rm -rf "$tmp_dir"
}

ensure_projectdiscovery_tool() {
    local tool="$1"
    local repo="$2"
    if command -v "$tool" &> /dev/null; then
        return 0
    fi
    local tag
    tag="$(github_latest_tag "$repo")"
    if [ -z "$tag" ]; then
        return 0
    fi
    local ver="${tag#v}"
    local arch="$(uname -m)"
    if [ "$arch" = "x86_64" ]; then
        arch="amd64"
    elif [ "$arch" = "aarch64" ]; then
        arch="arm64"
    fi
    local filename="${tool}_${ver}_linux_${arch}.zip"
    local url="https://github.com/${repo}/releases/download/${tag}/${filename}"
    echo -e "${YELLOW}[INFO] Installing ${tool} from GitHub release...${NC}"
    install_zip_binary "$url" "$tool" || echo -e "${YELLOW}[WARNING] Failed to install ${tool} from GitHub. Please install manually.${NC}"
}

ensure_dirsearch_fallback() {
    if command -v dirsearch &> /dev/null; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing dirsearch from source...${NC}"
    mkdir -p .tools
    if [ ! -d ".tools/dirsearch/.git" ]; then
        git clone --depth 1 https://github.com/maurosoria/dirsearch.git .tools/dirsearch
    else
        (cd .tools/dirsearch && git pull --ff-only) || true
    fi
    sudo tee /usr/local/bin/dirsearch >/dev/null <<EOF
#!/usr/bin/env bash
exec python3 "$(pwd)/.tools/dirsearch/dirsearch.py" "\$@"
EOF
    sudo chmod +x /usr/local/bin/dirsearch
}

ensure_searchsploit_fallback() {
    if command -v searchsploit &> /dev/null; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing Exploit-DB (searchsploit) from source...${NC}"
    mkdir -p .tools
    if [ ! -d ".tools/exploitdb/.git" ]; then
        git clone --depth 1 https://gitlab.com/exploit-database/exploitdb.git .tools/exploitdb
    else
        (cd .tools/exploitdb && git pull --ff-only) || true
    fi
    sudo ln -sf "$(pwd)/.tools/exploitdb/searchsploit" /usr/local/bin/searchsploit
    sudo chmod +x "$(pwd)/.tools/exploitdb/searchsploit" || true
}

ensure_browser_fallback() {
    has_browser=0
    for b in "${BROWSER_CANDIDATES[@]}"; do
        if command -v "$b" &> /dev/null; then
            has_browser=1
            break
        fi
    done
    if [ $has_browser -eq 1 ]; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing a headless-capable browser (chromium)...${NC}"
    sudo apt-get install -y chromium || sudo apt-get install -y firefox-esr || sudo apt-get install -y firefox || true
}

ensure_metasploit_optional() {
    if command -v msfconsole &> /dev/null; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Optional: Metasploit not found. Skipping auto-install by default.${NC}"
    echo -e "${YELLOW}[TIP] If you want to install Metasploit automatically, run:${NC}"
    echo -e "${YELLOW}      AUTO_INSTALL_METASPLOIT=1 ./run.sh${NC}"
    if [ "${AUTO_INSTALL_METASPLOIT:-0}" != "1" ]; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing Metasploit (metasploit-framework)...${NC}"
    sudo apt-get "${APT_GET_OPTS[@]}" update
    sudo apt-get "${APT_GET_OPTS[@]}" install -y metasploit-framework || true
}

ensure_projectdiscovery_tool "nuclei" "projectdiscovery/nuclei"
ensure_projectdiscovery_tool "subfinder" "projectdiscovery/subfinder"
ensure_dirsearch_fallback
ensure_searchsploit_fallback
ensure_browser_fallback
ensure_metasploit_optional

echo -e "${YELLOW}[INFO] Checking tool catalog dependencies (config/tools/*.yaml)...${NC}"
CATALOG_PKGS="$(python3 scripts/check_tool_catalog_deps.py --pm apt --print-packages 2>/dev/null || true)"
if [ -n "${CATALOG_PKGS:-}" ]; then
    echo -e "${YELLOW}[INFO] Installing extra packages for tool catalog: ${CATALOG_PKGS}${NC}"
    sudo apt-get update
    FAILED_CATALOG_PKGS=()
    for pkg in ${CATALOG_PKGS}; do
        sudo apt-get install -y "$pkg" || FAILED_CATALOG_PKGS+=("$pkg")
    done
    if [ ${#FAILED_CATALOG_PKGS[@]} -ne 0 ]; then
        echo -e "${YELLOW}[WARNING] Some catalog packages failed to install: ${FAILED_CATALOG_PKGS[*]}${NC}"
    fi
else
    echo -e "${GREEN}[INFO] Tool catalog dependency check completed.${NC}"
fi

# 3. Python Environment (venv)
VENV_DIR="venv"
if ! python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"; then
    echo -e "${RED}[ERROR] Python 3.10+ is required.${NC}"
    python3 --version || true
    exit 1
fi
if python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,13) else 1)"; then
    echo -e "${YELLOW}[WARNING] Detected Python 3.13+. Some third-party dependencies may not be fully compatible yet.${NC}"
    echo -e "${YELLOW}[TIP] If you encounter install/runtime issues, use Python 3.10-3.12 and re-run run.sh.${NC}"
fi
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}[INFO] Creating Python virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to create venv. Please install python3-venv.${NC}"
        echo "Try: sudo apt-get install python3-venv"
        exit 1
    fi
fi

VENV_PY="$VENV_DIR/bin/python3"
if [ ! -x "$VENV_PY" ]; then
    VENV_PY="$VENV_DIR/bin/python"
fi
if [ ! -x "$VENV_PY" ]; then
    echo -e "${RED}[ERROR] Virtual environment python not found at $VENV_DIR/bin/python3. ${NC}"
    echo -e "${YELLOW}[TIP] Ensure you run with: bash run.sh  (do not use: sh run.sh)${NC}"
    exit 1
fi

# 4. Python Dependencies (pip)
echo -e "${YELLOW}[INFO] Installing/Updating Python packages...${NC}"

# Clean pip cache to free up space
rm -rf ~/.cache/pip

# Fix "No space left on device" error:
# Sometimes /tmp is a small tmpfs (RAM disk). We force pip to use the disk partition.
TMPDIR_PIP="$(pwd)/tmp_pip_install"
mkdir -p "$TMPDIR_PIP"

# Use pip cache to speed up (re-enabled after clean)
"$VENV_PY" -m pip install --upgrade pip > /dev/null 2>&1

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
if [ -z "${PIP_INDEX_URL:-}" ]; then
    export PIP_INDEX_URL="$PIP_INDEX_URL_DEFAULT"
    echo -e "${YELLOW}[INFO] Using PIP_INDEX_URL=${PIP_INDEX_URL}${NC}"
fi
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

# Install torch CPU version EXPLICITLY to avoid downloading nvidia_nccl (300MB+)
# We install sentence-transformers dependencies manually first to ensure they pick up the CPU torch
TMPDIR="$TMPDIR_PIP" "$VENV_PY" -m pip install --retries 10 --timeout 120 torch torchvision torchaudio --index-url "$TORCH_INDEX_URL" --cache-dir "$TMPDIR_PIP"

# Force reinstall requirements, but allow skipping satisfied packages to avoid re-triggering GPU torch download
TMPDIR="$TMPDIR_PIP" "$VENV_PY" -m pip install --retries 10 --timeout 120 -r requirements.txt --cache-dir "$TMPDIR_PIP"

# Clean up temp dir
rm -rf "$TMPDIR_PIP"
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to install Python requirements. Trying with --break-system-packages if needed (though venv should protect).${NC}"
    # Just exit for now, as venv is active.
    exit 1
fi

# Ensure runtime TMPDIR does not point to a project directory (avoids PulseAudio and other runtime permission issues)
unset TMPDIR

# 5. Dependency Check (Final Verification)
echo -e "${YELLOW}[INFO] Verifying environment...${NC}"
"$VENV_PY" scripts/check_deps.py
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Missing required dependencies. Please fix and re-run.${NC}"
    echo -e "${YELLOW}[TIP] If you want to allow missing tools, run without STRICT_DEPS=1 (default).${NC}"
    exit 1
fi

# 6. RAG Initialization
echo -e "${YELLOW}[INFO] Initializing Knowledge Base (RAG)...${NC}"
# Use HF Mirror to avoid connection timeout in China
"$VENV_PY" scripts/init_rag.py
if [ $? -ne 0 ]; then
    echo -e "${RED}[WARNING] RAG Initialization failed. Semantic search might be unavailable.${NC}"
fi

# 7. Launch
echo ""
echo -e "${GREEN}[SUCCESS] Environment ready! Starting AutoPentestAI...${NC}"
echo -e "${GREEN}[INFO] Web UI: http://localhost:8000${NC}"
echo ""

# Function to open browser
open_browser() {
    sleep 3
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8000
    elif command -v firefox &> /dev/null; then
        firefox http://localhost:8000 &
    fi
}

# Run browser opener in background
open_browser &

# Start Server
"$VENV_PY" -m src.main
