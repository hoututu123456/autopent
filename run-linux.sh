#!/usr/bin/env bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

set -euo pipefail

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}      AutoPentestAI - Cross-Distro Linux Launcher${NC}"
echo -e "${GREEN}   (Debian/Ubuntu/CentOS/RHEL/Rocky/Alma support)${NC}"
echo -e "${GREEN}==================================================${NC}"

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

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Missing command: $1${NC}"
        exit 1
    fi
}

sudo_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

detect_platform() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_LIKE="${ID_LIKE:-}"
    else
        OS_ID="unknown"
        OS_LIKE=""
    fi

    PKG_MGR=""
    if command -v apt-get >/dev/null 2>&1; then
        PKG_MGR="apt"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MGR="yum"
    fi

    if [ -z "$PKG_MGR" ]; then
        echo -e "${RED}[ERROR] No supported package manager found (apt/dnf/yum).${NC}"
        exit 1
    fi

    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64|amd64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        armv7l) ARCH="armv7" ;;
    esac

    if [ "$PKG_MGR" = "apt" ]; then
        APT_GET_OPTS=(-o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)
    else
        APT_GET_OPTS=()
    fi
}

install_packages() {
    local pkgs=("$@")
    if [ "${#pkgs[@]}" -eq 0 ]; then
        return 0
    fi

    if [ "$PKG_MGR" = "apt" ]; then
        sudo_cmd apt-get "${APT_GET_OPTS[@]}" update -y
        local failed=()
        for p in "${pkgs[@]}"; do
            sudo_cmd apt-get "${APT_GET_OPTS[@]}" install -y "$p" || failed+=("$p")
        done
        if [ "${#failed[@]}" -ne 0 ]; then
            echo -e "${YELLOW}[WARNING] Some packages failed to install (apt): ${failed[*]}${NC}"
        fi
        return 0
    fi

    if [ "$PKG_MGR" = "dnf" ]; then
        sudo_cmd dnf makecache -y
        local failed=()
        for p in "${pkgs[@]}"; do
            sudo_cmd dnf install -y "$p" || failed+=("$p")
        done
        if [ "${#failed[@]}" -ne 0 ]; then
            echo -e "${YELLOW}[WARNING] Some packages failed to install (dnf): ${failed[*]}${NC}"
        fi
        return 0
    fi

    if [ "$PKG_MGR" = "yum" ]; then
        sudo_cmd yum makecache -y || true
        local failed=()
        for p in "${pkgs[@]}"; do
            sudo_cmd yum install -y "$p" || failed+=("$p")
        done
        if [ "${#failed[@]}" -ne 0 ]; then
            echo -e "${YELLOW}[WARNING] Some packages failed to install (yum): ${failed[*]}${NC}"
        fi
        return 0
    fi
}

ensure_env_file() {
    if [ ! -f .env ]; then
        echo -e "${YELLOW}[INFO] .env not found. Creating from example...${NC}"
        if [ -f .env.example ]; then
            cp .env.example .env
        else
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
        fi
        echo -e "${GREEN}[SUCCESS] Created .env file.${NC}"
    fi

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
            sed -i "s/^AI_BIND_INTERFACE=.*/AI_BIND_INTERFACE=$default_iface/" .env || true
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
}

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

download_to_tmp() {
    local url="$1"
    local out="$2"
    if curl_retry "$url" -o "$out"; then
        return 0
    fi
    if [ "$USE_GHPROXY" = "1" ]; then
        curl_retry "${GHPROXY_PREFIX}${url}" -o "$out"
        return $?
    fi
    return 1
}

install_zip_binary() {
    local url="$1"
    local bin_name="$2"
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    local zip_path="$tmp_dir/pkg.zip"
    if ! download_to_tmp "$url" "$zip_path"; then
        rm -rf "$tmp_dir"
        return 1
    fi
    if ! unzip -q "$zip_path" -d "$tmp_dir"; then
        rm -rf "$tmp_dir"
        return 1
    fi
    if [ ! -f "$tmp_dir/$bin_name" ]; then
        if [ -f "$tmp_dir/$bin_name/$bin_name" ]; then
            mv "$tmp_dir/$bin_name/$bin_name" "$tmp_dir/$bin_name"
        fi
    fi
    if [ ! -f "$tmp_dir/$bin_name" ]; then
        rm -rf "$tmp_dir"
        return 1
    fi
    sudo_cmd install -m 0755 "$tmp_dir/$bin_name" /usr/local/bin/"$bin_name"
    rm -rf "$tmp_dir"
}

ensure_projectdiscovery_tool() {
    local tool="$1"
    local repo="$2"
    if command -v "$tool" >/dev/null 2>&1; then
        return 0
    fi
    local tag
    tag="$(github_latest_tag "$repo")"
    if [ -z "$tag" ]; then
        echo -e "${YELLOW}[WARNING] Could not resolve latest version for $tool from GitHub.${NC}"
        return 0
    fi
    local ver="${tag#v}"
    local filename="${tool}_${ver}_linux_${ARCH}.zip"
    local url="https://github.com/${repo}/releases/download/${tag}/${filename}"
    echo -e "${YELLOW}[INFO] Installing ${tool} (${tag}) from ${url}${NC}"
    if ! install_zip_binary "$url" "$tool"; then
        echo -e "${YELLOW}[WARNING] Failed to install ${tool} from GitHub release. You may need to install it manually.${NC}"
    fi
}

ensure_feroxbuster() {
    if command -v feroxbuster >/dev/null 2>&1; then
        return 0
    fi
    local json
    json="$(curl -sL "https://api.github.com/repos/epi052/feroxbuster/releases/latest" || true)"
    if [ -z "$json" ]; then
        echo -e "${YELLOW}[WARNING] Could not resolve latest feroxbuster version from GitHub.${NC}"
        return 0
    fi
    local arch_token=""
    if [ "$ARCH" = "amd64" ]; then
        arch_token="x86_64"
    elif [ "$ARCH" = "arm64" ]; then
        arch_token="aarch64"
    else
        echo -e "${YELLOW}[WARNING] feroxbuster installer does not support arch=$ARCH; skipping.${NC}"
        return 0
    fi

    local url
    url="$(echo "$json" | grep -oE '"browser_download_url":[ ]*"[^"]+"' | sed -n 's/.*"browser_download_url":[ ]*"\([^"]*\)".*/\1/p' | grep -i "linux" | grep -i "musl" | grep -i "$arch_token" | grep -i "\.zip$" | head -n 1)"
    if [ -z "$url" ]; then
        echo -e "${YELLOW}[WARNING] Could not find a suitable feroxbuster asset for arch=$ARCH.${NC}"
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing feroxbuster from ${url}${NC}"
    if ! install_zip_binary "$url" "feroxbuster"; then
        echo -e "${YELLOW}[WARNING] Failed to install feroxbuster. You may install it manually.${NC}"
    fi
}

ensure_dirsearch() {
    if command -v dirsearch >/dev/null 2>&1; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing dirsearch from source...${NC}"
    local dst_dir=".tools/dirsearch"
    mkdir -p .tools
    if [ ! -d "$dst_dir/.git" ]; then
        git clone --depth 1 https://github.com/maurosoria/dirsearch.git "$dst_dir"
    else
        (cd "$dst_dir" && git pull --ff-only) || true
    fi
    sudo_cmd tee /usr/local/bin/dirsearch >/dev/null <<EOF
#!/usr/bin/env bash
exec python3 "$(pwd)/$dst_dir/dirsearch.py" "\$@"
EOF
    sudo_cmd chmod +x /usr/local/bin/dirsearch
}

ensure_searchsploit() {
    if command -v searchsploit >/dev/null 2>&1; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing Exploit-DB (searchsploit) from source...${NC}"
    local dst_dir=".tools/exploitdb"
    mkdir -p .tools
    if [ ! -d "$dst_dir/.git" ]; then
        git clone --depth 1 https://gitlab.com/exploit-database/exploitdb.git "$dst_dir"
    else
        (cd "$dst_dir" && git pull --ff-only) || true
    fi
    sudo_cmd ln -sf "$(pwd)/$dst_dir/searchsploit" /usr/local/bin/searchsploit
    sudo_cmd chmod +x "$(pwd)/$dst_dir/searchsploit" || true
}

ensure_browser() {
    if command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 || command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1 || command -v firefox >/dev/null 2>&1; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Installing a headless-capable browser (chromium or firefox)...${NC}"
    if [ "$PKG_MGR" = "apt" ]; then
        install_packages chromium || install_packages firefox-esr || install_packages firefox || true
    else
        install_packages chromium || install_packages chromium-headless || install_packages firefox || true
    fi
}

ensure_metasploit_optional() {
    if command -v msfconsole >/dev/null 2>&1; then
        return 0
    fi
    echo -e "${YELLOW}[INFO] Optional: Metasploit not found. Skipping auto-install by default.${NC}"
    echo -e "${YELLOW}[TIP] If you want to install Metasploit automatically, run:${NC}"
    echo -e "${YELLOW}      AUTO_INSTALL_METASPLOIT=1 ./run-linux.sh${NC}"

    if [ "${AUTO_INSTALL_METASPLOIT:-0}" != "1" ]; then
        return 0
    fi

    echo -e "${YELLOW}[INFO] Installing Metasploit via Rapid7 installer...${NC}"
    if ! curl -fsSL https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfinstall -o /tmp/msfinstall; then
        echo -e "${YELLOW}[WARNING] Could not download msfinstall. Please install Metasploit manually.${NC}"
        return 0
    fi
    sudo_cmd chmod +x /tmp/msfinstall
    sudo_cmd /tmp/msfinstall || true
}

ensure_system_tools() {
    echo -e "${YELLOW}[INFO] Installing system dependencies...${NC}"

    if [ "$PKG_MGR" = "apt" ]; then
        install_packages ca-certificates curl wget unzip tar git jq \
            python3 python3-venv python3-pip python3-dev build-essential \
            nmap sqlmap gobuster hydra ncat \
            nikto dirb \
            john hashcat radare2 binwalk binutils \
            openssh-client \
            enum4linux-ng enum4linux smbmap nbtscan responder samba-common-bin netexec || true
    else
        install_packages epel-release || true
        install_packages ca-certificates curl wget unzip tar git jq \
            python3 python3-pip python3-devel gcc make \
            nmap sqlmap \
            openssh-clients \
            binutils
        install_packages python3-virtualenv || true
        install_packages gobuster hydra nmap-ncat nikto dirb john hashcat radare2 binwalk || true
        install_packages samba-client samba-common-tools || true
    fi

    ensure_browser
    ensure_projectdiscovery_tool "nuclei" "projectdiscovery/nuclei"
    ensure_projectdiscovery_tool "subfinder" "projectdiscovery/subfinder"
    ensure_dirsearch
    ensure_searchsploit
    ensure_feroxbuster
    ensure_metasploit_optional

    echo -e "${YELLOW}[INFO] Checking tool catalog dependencies (config/tools/*.yaml)...${NC}"
    local catalog_pkgs
    catalog_pkgs="$(python3 scripts/check_tool_catalog_deps.py --pm "$PKG_MGR" --print-packages 2>/dev/null || true)"
    if [ -n "${catalog_pkgs:-}" ]; then
        echo -e "${YELLOW}[INFO] Installing extra packages for tool catalog: ${catalog_pkgs}${NC}"
        install_packages ${catalog_pkgs}
    fi
}

ensure_venv_and_python_deps() {
    local venv_dir="venv"
    if ! python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"; then
        echo -e "${RED}[ERROR] Python 3.10+ is required.${NC}"
        python3 --version || true
        exit 1
    fi
    if python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,13) else 1)"; then
        echo -e "${YELLOW}[WARNING] Detected Python 3.13+. Some third-party dependencies may not be fully compatible yet.${NC}"
        echo -e "${YELLOW}[TIP] If you encounter install/runtime issues, use Python 3.10-3.12 and re-run run-linux.sh.${NC}"
    fi
    if [ ! -d "$venv_dir" ]; then
        echo -e "${YELLOW}[INFO] Creating Python virtual environment...${NC}"
        python3 -m venv "$venv_dir"
    fi

    local venv_py="$venv_dir/bin/python3"
    if [ ! -x "$venv_py" ]; then
        venv_py="$venv_dir/bin/python"
    fi
    if [ ! -x "$venv_py" ]; then
        echo -e "${RED}[ERROR] Virtual environment python not found at $venv_dir/bin/python3.${NC}"
        exit 1
    fi

    echo -e "${YELLOW}[INFO] Installing/Updating Python packages (venv)...${NC}"
    rm -rf ~/.cache/pip || true
    local tmpdir_pip
    tmpdir_pip="$(pwd)/tmp_pip_install"
    mkdir -p "$tmpdir_pip"

    export PIP_DISABLE_PIP_VERSION_CHECK=1
    export PIP_NO_INPUT=1
    export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
    if [ -z "${PIP_INDEX_URL:-}" ]; then
        export PIP_INDEX_URL="$PIP_INDEX_URL_DEFAULT"
        echo -e "${YELLOW}[INFO] Using PIP_INDEX_URL=${PIP_INDEX_URL}${NC}"
    fi
    export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

    "$venv_py" -m pip install --upgrade pip > /dev/null 2>&1 || true
    TMPDIR="$tmpdir_pip" "$venv_py" -m pip install --retries 10 --timeout 120 torch torchvision torchaudio --index-url "$TORCH_INDEX_URL" --cache-dir "$tmpdir_pip"
    TMPDIR="$tmpdir_pip" "$venv_py" -m pip install --retries 10 --timeout 120 -r requirements.txt --cache-dir "$tmpdir_pip"
    rm -rf "$tmpdir_pip" || true

    echo -e "${YELLOW}[INFO] Verifying environment...${NC}"
    if ! "$venv_py" scripts/check_deps.py; then
        echo -e "${RED}[ERROR] Dependency check failed. Please fix and re-run.${NC}"
        echo -e "${YELLOW}[TIP] Set STRICT_DEPS=1 for strict tool checks; otherwise only core deps are enforced.${NC}"
        exit 1
    fi

    echo -e "${YELLOW}[INFO] Initializing Knowledge Base (RAG)...${NC}"
    "$venv_py" scripts/init_rag.py || echo -e "${YELLOW}[WARNING] RAG init failed; semantic search may be unavailable.${NC}"

    echo ""
    echo -e "${GREEN}[SUCCESS] Environment ready! Starting AutoPentestAI...${NC}"
    echo -e "${GREEN}[INFO] Web UI: http://localhost:8000${NC}"
    echo ""

    if command -v xdg-open >/dev/null 2>&1; then
        (sleep 3 && xdg-open http://localhost:8000) >/dev/null 2>&1 || true
    fi

    "$venv_py" -m src.main
}

main() {
    need_cmd curl
    need_cmd sed
    detect_platform
    ensure_env_file
    apply_proxy_from_env
    ensure_system_tools
    ensure_venv_and_python_deps
}

main "$@"
