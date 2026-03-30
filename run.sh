#!/bin/bash
#
# MieMie-Studio 控制面板
#
# 用法:
#   ./run.sh              - 打开交互式控制面板（推荐）
#   ./run.sh [命令]       - 直接执行命令（适用于脚本/自动化）
#
# 命令行模式:
#   start [--prod]  stop  restart [--prod]  status  logs  install  test
#   update [--auto]  auto-update [enable|disable|status]  rollback  optimize
#   network [on|off|status]  port [backend|frontend] <端口>  version  help
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Screen 会话名称
BACKEND_SESSION="miemie-studio-backend"
FRONTEND_SESSION="miemie-studio-frontend"

# 日志文件
LOG_DIR="$PROJECT_DIR/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# 运行模式：dev (默认) 或 prod
RUN_MODE="${MIEMIE_MODE:-dev}"

# ======================
# 工具函数
# ======================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 未安装，请先安装"
        return 1
    fi
    return 0
}

# ======================
# 环境检查与自动安装
# ======================

# 检测系统包管理器
detect_pkg_manager() {
    if command -v apt-get &> /dev/null; then
        echo "apt"
    elif command -v yum &> /dev/null; then
        echo "yum"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v brew &> /dev/null; then
        echo "brew"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    else
        echo ""
    fi
}

# 用 sudo 或直接执行（取决于是否为 root）
run_pkg_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# 自动安装系统包
auto_install_package() {
    local pkg_name="$1"
    local display_name="${2:-$pkg_name}"
    local pkg_mgr
    pkg_mgr=$(detect_pkg_manager)

    if [ -z "$pkg_mgr" ]; then
        log_error "无法检测系统包管理器，请手动安装 $display_name"
        return 1
    fi

    log_info "正在自动安装 $display_name ..."

    case "$pkg_mgr" in
        apt)
            run_pkg_cmd apt-get update -qq
            run_pkg_cmd apt-get install -y -qq "$pkg_name"
            ;;
        yum)
            run_pkg_cmd yum install -y -q "$pkg_name"
            ;;
        dnf)
            run_pkg_cmd dnf install -y -q "$pkg_name"
            ;;
        brew)
            brew install "$pkg_name"
            ;;
        pacman)
            run_pkg_cmd pacman -S --noconfirm "$pkg_name"
            ;;
    esac

    if [ $? -eq 0 ]; then
        log_success "$display_name 安装完成"
        return 0
    else
        log_error "$display_name 安装失败，请手动安装"
        return 1
    fi
}

check_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        log_error "Python 未安装"
        exit 1
    fi
}

# 自动安装 python3-venv / ensurepip 包
install_python_venv_package() {
    local PYTHON
    PYTHON=$(check_python)
    local py_version
    py_version=$($PYTHON --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')

    log_warn "Python venv/ensurepip 模块不可用，正在自动安装..."

    local pkg_mgr
    pkg_mgr=$(detect_pkg_manager)

    case "$pkg_mgr" in
        apt)
            local venv_pkg="python${py_version}-venv"
            log_info "执行: apt-get install $venv_pkg ..."
            run_pkg_cmd apt-get update -qq
            run_pkg_cmd apt-get install -y "$venv_pkg"
            ;;
        yum|dnf)
            auto_install_package "python3-virtualenv" "Python venv"
            ;;
        brew)
            log_info "macOS 的 Python 自带 venv，请检查 Python 安装是否完整"
            return 1
            ;;
        pacman)
            auto_install_package "python" "Python (含 venv)"
            ;;
        *)
            log_error "无法自动安装，请手动执行: apt install python${py_version}-venv"
            return 1
            ;;
    esac
}

# 自动安装 Node.js（使用 NodeSource 或系统包管理器）
install_node() {
    local pkg_mgr
    pkg_mgr=$(detect_pkg_manager)

    log_info "正在自动安装 Node.js ..."

    case "$pkg_mgr" in
        apt)
            if ! command -v curl &> /dev/null; then
                run_pkg_cmd apt-get update -qq
                run_pkg_cmd apt-get install -y -qq curl
            fi
            # NodeSource 官方安装脚本（Node.js 20 LTS）
            log_info "通过 NodeSource 安装 Node.js 20 LTS ..."
            curl -fsSL https://deb.nodesource.com/setup_20.x | run_pkg_cmd bash -
            run_pkg_cmd apt-get install -y -qq nodejs
            ;;
        yum|dnf)
            if ! command -v curl &> /dev/null; then
                run_pkg_cmd "$pkg_mgr" install -y -q curl
            fi
            curl -fsSL https://rpm.nodesource.com/setup_20.x | run_pkg_cmd bash -
            run_pkg_cmd "$pkg_mgr" install -y -q nodejs
            ;;
        brew)
            brew install node@20
            ;;
        pacman)
            run_pkg_cmd pacman -S --noconfirm nodejs npm
            ;;
        *)
            log_error "无法自动安装 Node.js，请手动安装 Node.js 18+ 后重试"
            log_info "推荐: https://nodejs.org/en/download/"
            return 1
            ;;
    esac

    if command -v node &> /dev/null; then
        local node_ver
        node_ver=$(node --version)
        log_success "Node.js $node_ver 安装完成"
        return 0
    else
        log_error "Node.js 安装失败，请手动安装"
        return 1
    fi
}

check_node() {
    if ! command -v node &> /dev/null; then
        install_node || exit 1
    fi
}

check_npm() {
    if ! command -v npm &> /dev/null; then
        log_error "npm 未安装（Node.js 安装可能不完整）"
        install_node || exit 1
    fi
}

# 确保 screen 已安装
ensure_screen() {
    if command -v screen &> /dev/null; then
        return 0
    fi

    local pkg_mgr
    pkg_mgr=$(detect_pkg_manager)

    case "$pkg_mgr" in
        apt)      auto_install_package "screen" "screen" ;;
        yum|dnf)  auto_install_package "screen" "screen" ;;
        brew)     auto_install_package "screen" "screen" ;;
        pacman)   auto_install_package "screen" "screen" ;;
        *)
            log_error "screen 未安装，请手动安装"
            return 1
            ;;
    esac
}

check_screen() {
    ensure_screen || exit 1
}

# 确保 lsof 已安装（端口检查/状态展示依赖）
ensure_lsof() {
    if command -v lsof &> /dev/null; then
        return 0
    fi

    log_warn "lsof 未安装，正在自动安装..."

    case "$(detect_pkg_manager)" in
        apt)      auto_install_package "lsof" "lsof" ;;
        yum|dnf)  auto_install_package "lsof" "lsof" ;;
        brew)     auto_install_package "lsof" "lsof" ;;
        pacman)   auto_install_package "lsof" "lsof" ;;
        *)
            log_error "lsof 未安装，请手动安装"
            return 1
            ;;
    esac
}

check_lsof() {
    ensure_lsof || exit 1
}

# 确保 FFmpeg/FFprobe 已安装（视频尾帧提取、视频拼接、视频编辑依赖）
ensure_ffmpeg() {
    if command -v ffmpeg &> /dev/null && command -v ffprobe &> /dev/null; then
        return 0
    fi

    log_warn "FFmpeg/FFprobe 未安装，正在自动安装..."

    case "$(detect_pkg_manager)" in
        apt)      auto_install_package "ffmpeg" "FFmpeg" ;;
        yum|dnf)  auto_install_package "ffmpeg" "FFmpeg" ;;
        brew)     auto_install_package "ffmpeg" "FFmpeg" ;;
        pacman)   auto_install_package "ffmpeg" "FFmpeg" ;;
        *)
            log_error "FFmpeg/FFprobe 未安装，请手动安装 ffmpeg"
            return 1
            ;;
    esac

    if command -v ffmpeg &> /dev/null && command -v ffprobe &> /dev/null; then
        return 0
    fi

    log_error "FFmpeg 已尝试安装，但 ffmpeg/ffprobe 仍不可用"
    return 1
}

check_ffmpeg() {
    ensure_ffmpeg || exit 1
}

# ======================
# 虚拟环境管理
# ======================

venv_exists() {
    [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]
}

create_venv() {
    if venv_exists; then
        log_info "虚拟环境已存在"
        return 0
    fi

    local PYTHON
    PYTHON=$(check_python)

    log_info "创建虚拟环境..."

    # 第一次尝试
    local venv_output
    if venv_output=$($PYTHON -m venv "$VENV_DIR" 2>&1); then
        log_success "虚拟环境创建完成"
        return 0
    fi

    # 创建失败——检测是否因为缺少 ensurepip / python3-venv
    if echo "$venv_output" | grep -qiE "ensurepip|python3.*-venv|venv.*not.*available"; then
        # 清理失败的半成品目录
        rm -rf "$VENV_DIR"

        install_python_venv_package || {
            log_error "虚拟环境创建失败，请根据上方提示手动安装后重试"
            exit 1
        }

        # 第二次尝试
        log_info "重新创建虚拟环境..."
        if $PYTHON -m venv "$VENV_DIR"; then
            log_success "虚拟环境创建完成"
            return 0
        fi
    fi

    # 其他原因失败
    log_error "虚拟环境创建失败:"
    echo "$venv_output"
    rm -rf "$VENV_DIR"
    exit 1
}

activate_venv() {
    if ! venv_exists; then
        create_venv
    fi
    source "$VENV_DIR/bin/activate"
}

# ======================
# 依赖管理
# ======================

REQUIRED_BACKEND_PACKAGES=(
    fastapi
    uvicorn
    python-multipart
    pydantic
    dashscope
    python-docx
    pypdf
    httpx
    slowapi
    oss2
    Pillow
    opencv-python-headless
    bcrypt
    python-dotenv
    pytest
    pytest-asyncio
)

REQUIRED_BACKEND_PROD_PACKAGES=(
    gunicorn
)

python_packages_installed() {
    local pip_bin="$VENV_DIR/bin/pip"
    local package_name

    if [ ! -x "$pip_bin" ]; then
        return 1
    fi

    for package_name in "$@"; do
        if ! "$pip_bin" show "$package_name" &> /dev/null; then
            return 1
        fi
    done

    return 0
}

backend_deps_installed() {
    if ! venv_exists; then
        return 1
    fi
    python_packages_installed "${REQUIRED_BACKEND_PACKAGES[@]}"
}

backend_prod_deps_installed() {
    if ! venv_exists; then
        return 1
    fi
    python_packages_installed "${REQUIRED_BACKEND_PROD_PACKAGES[@]}"
}

frontend_deps_installed() {
    [ -d "$FRONTEND_DIR/node_modules" ] && [ -f "$FRONTEND_DIR/node_modules/.package-lock.json" ]
}

install_backend_deps() {
    log_info "检查后端依赖..."

    check_ffmpeg

    create_venv
    
    if backend_deps_installed; then
        log_info "后端依赖已安装"
        return 0
    fi
    
    log_info "安装后端依赖..."
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    log_success "后端依赖安装完成"
}

install_frontend_deps() {
    log_info "检查前端依赖..."
    check_node
    check_npm
    
    if frontend_deps_installed; then
        log_info "前端依赖已安装"
        return 0
    fi
    
    log_info "安装前端依赖..."
    cd "$FRONTEND_DIR"
    npm install
    cd "$PROJECT_DIR"
    log_success "前端依赖安装完成"
}

install_all_deps() {
    maybe_offer_performance_profile "install" "false"
    install_backend_deps
    install_frontend_deps
    log_success "所有依赖安装完成"
}

# ======================
# 端口与网络配置
# ======================

BACKEND_PORT=8000
FRONTEND_PORT=3000
MIEMIE_CONF="$PROJECT_DIR/.miemie.conf"

# 默认仅本地访问
LISTEN_HOST="127.0.0.1"
ALLOWED_DOMAINS=""
ENV_MIEMIE_WORKERS="${MIEMIE_WORKERS:-}"
ENV_NODE_BUILD_MEMORY_MB="${NODE_BUILD_MEMORY_MB:-}"
MIEMIE_WORKERS="$ENV_MIEMIE_WORKERS"
NODE_BUILD_MEMORY_MB="$ENV_NODE_BUILD_MEMORY_MB"
PERF_PROFILE_APPLIED="false"
PERF_PROFILE_SIGNATURE=""
SWAPFILE_PATH="/swapfile.miemie"

# 从配置文件加载持久化设置
load_config() {
    local env_backend_port="${MIEMIE_BACKEND_PORT:-}"
    local env_frontend_port="${MIEMIE_FRONTEND_PORT:-}"
    local env_workers="$ENV_MIEMIE_WORKERS"
    local env_node_build_memory_mb="$ENV_NODE_BUILD_MEMORY_MB"

    if [ -f "$MIEMIE_CONF" ]; then
        source "$MIEMIE_CONF"
    fi

    # 环境变量优先级最高
    BACKEND_PORT="${env_backend_port:-$BACKEND_PORT}"
    FRONTEND_PORT="${env_frontend_port:-$FRONTEND_PORT}"
    MIEMIE_WORKERS="${env_workers:-$MIEMIE_WORKERS}"
    NODE_BUILD_MEMORY_MB="${env_node_build_memory_mb:-$NODE_BUILD_MEMORY_MB}"
}

# 保存设置到配置文件
save_config() {
    cat > "$MIEMIE_CONF" << EOF
# MieMie-Studio 运行配置（自动生成，勿手动编辑）
LISTEN_HOST="$LISTEN_HOST"
ALLOWED_DOMAINS="$ALLOWED_DOMAINS"
BACKEND_PORT="$BACKEND_PORT"
FRONTEND_PORT="$FRONTEND_PORT"
MIEMIE_WORKERS="$MIEMIE_WORKERS"
NODE_BUILD_MEMORY_MB="$NODE_BUILD_MEMORY_MB"
PERF_PROFILE_APPLIED="$PERF_PROFILE_APPLIED"
PERF_PROFILE_SIGNATURE="$PERF_PROFILE_SIGNATURE"
SWAPFILE_PATH="$SWAPFILE_PATH"
EOF
}

# 获取服务器本机 IP（非 127.0.0.1 的第一个 IPv4 地址）
get_server_ip() {
    local ip=""
    # 优先 hostname -I（Linux）
    if command -v hostname &> /dev/null; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
    # 回退 ip route（Linux）
    if [ -z "$ip" ] && command -v ip &> /dev/null; then
        ip=$(ip route get 1.1.1.1 2>/dev/null | sed -n 's/.*src \([0-9.]*\).*/\1/p')
    fi
    # 回退 ifconfig（macOS / Linux）
    if [ -z "$ip" ] && command -v ifconfig &> /dev/null; then
        ip=$(ifconfig 2>/dev/null | awk '/inet / && !/127.0.0.1/ {print $2; exit}')
    fi
    echo "${ip:-127.0.0.1}"
}

# 根据 LISTEN_HOST 生成 URL 中使用的主机名
get_display_host() {
    if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
        get_server_ip
    else
        echo "localhost"
    fi
}

get_default_gunicorn_workers() {
    local cpu_count=""

    if command -v nproc &> /dev/null; then
        cpu_count=$(nproc)
    elif command -v sysctl &> /dev/null; then
        cpu_count=$(sysctl -n hw.ncpu 2>/dev/null || true)
    fi

    if ! [[ "$cpu_count" =~ ^[0-9]+$ ]] || [ "$cpu_count" -le 0 ]; then
        cpu_count=1
    fi

    if [ "$cpu_count" -ge 2 ]; then
        echo 2
    else
        echo 1
    fi
}

is_interactive_shell() {
    [ -t 0 ] && [ -t 1 ]
}

get_os_name() {
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        source /etc/os-release
        if [ -n "${PRETTY_NAME:-}" ]; then
            echo "$PRETTY_NAME"
            return 0
        fi
        if [ -n "${NAME:-}" ]; then
            echo "${NAME}${VERSION_ID:+ $VERSION_ID}"
            return 0
        fi
    fi
    uname -s 2>/dev/null || echo "Unknown"
}

get_kernel_info() {
    uname -sr 2>/dev/null || uname -a 2>/dev/null || echo "Unknown"
}

get_cpu_cores() {
    local cpu_count=""
    if command -v nproc &> /dev/null; then
        cpu_count=$(nproc)
    elif command -v sysctl &> /dev/null; then
        cpu_count=$(sysctl -n hw.ncpu 2>/dev/null || true)
    fi

    if ! [[ "$cpu_count" =~ ^[0-9]+$ ]] || [ "$cpu_count" -le 0 ]; then
        cpu_count=1
    fi

    echo "$cpu_count"
}

get_total_memory_mb() {
    local mem_mb=""
    if [ -r /proc/meminfo ]; then
        mem_mb=$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo)
    elif command -v sysctl &> /dev/null; then
        local mem_bytes
        mem_bytes=$(sysctl -n hw.memsize 2>/dev/null || true)
        if [[ "$mem_bytes" =~ ^[0-9]+$ ]] && [ "$mem_bytes" -gt 0 ]; then
            mem_mb=$((mem_bytes / 1024 / 1024))
        fi
    fi

    if ! [[ "$mem_mb" =~ ^[0-9]+$ ]] || [ "$mem_mb" -le 0 ]; then
        mem_mb=1024
    fi

    echo "$mem_mb"
}

get_total_swap_mb() {
    local swap_mb=0

    if [ -r /proc/swaps ]; then
        swap_mb=$(awk 'NR>1 {sum += $3} END {print int(sum/1024)}' /proc/swaps)
    elif command -v sysctl &> /dev/null; then
        local swap_bytes
        swap_bytes=$(sysctl -n vm.swapusage 2>/dev/null | awk -F'[ =M]' '/total/ {print int($7)}' || true)
        if [[ "$swap_bytes" =~ ^[0-9]+$ ]] && [ "$swap_bytes" -gt 0 ]; then
            swap_mb=$swap_bytes
        fi
    fi

    if ! [[ "$swap_mb" =~ ^[0-9]+$ ]] || [ "$swap_mb" -lt 0 ]; then
        swap_mb=0
    fi

    echo "$swap_mb"
}

format_mb() {
    local value_mb="${1:-0}"
    if ! [[ "$value_mb" =~ ^[0-9]+$ ]]; then
        value_mb=0
    fi

    if [ "$value_mb" -ge 1024 ]; then
        awk -v mb="$value_mb" 'BEGIN {printf "%.1fGB", mb / 1024}'
    else
        echo "${value_mb}MB"
    fi
}

clamp_value() {
    local value="$1"
    local min_value="$2"
    local max_value="$3"

    if [ "$value" -lt "$min_value" ]; then
        echo "$min_value"
    elif [ "$value" -gt "$max_value" ]; then
        echo "$max_value"
    else
        echo "$value"
    fi
}

round_down_step() {
    local value="$1"
    local step="$2"

    if [ "$value" -lt "$step" ]; then
        echo "$value"
    else
        echo $(( (value / step) * step ))
    fi
}

recommend_gunicorn_workers() {
    local mem_mb="$1"
    local cpu_cores="$2"
    local max_by_mem=1

    if [ "$mem_mb" -ge 12288 ]; then
        max_by_mem=4
    elif [ "$mem_mb" -ge 8192 ]; then
        max_by_mem=3
    elif [ "$mem_mb" -ge 4096 ]; then
        max_by_mem=2
    fi

    if [ "$cpu_cores" -lt "$max_by_mem" ]; then
        echo "$cpu_cores"
    else
        echo "$max_by_mem"
    fi
}

recommend_node_build_memory_mb() {
    local mem_mb="$1"
    local target_mb=$(( mem_mb * 60 / 100 ))

    target_mb=$(clamp_value "$target_mb" 768 4096)
    target_mb=$(round_down_step "$target_mb" 256)

    if [ "$target_mb" -lt 768 ]; then
        target_mb=768
    fi

    echo "$target_mb"
}

recommend_swap_mb() {
    local mem_mb="$1"
    local swap_mb="$2"

    if [ "$(uname -s)" != "Linux" ]; then
        echo 0
        return 0
    fi

    if [ "$mem_mb" -lt 4096 ] && [ "$swap_mb" -lt 2048 ]; then
        echo 2048
    else
        echo 0
    fi
}

build_perf_profile_signature() {
    local kernel="$1"
    local mem_mb="$2"
    local cpu_cores="$3"
    echo "${kernel}|${mem_mb}|${cpu_cores}"
}

append_line_if_missing() {
    local file_path="$1"
    local line="$2"

    if grep -Fqx "$line" "$file_path" 2>/dev/null; then
        return 0
    fi

    if [ "$(id -u)" -eq 0 ]; then
        printf '%s\n' "$line" >> "$file_path"
    else
        printf '%s\n' "$line" | sudo tee -a "$file_path" >/dev/null
    fi
}

show_server_profile_summary() {
    local os_name="$1"
    local kernel="$2"
    local cpu_cores="$3"
    local mem_mb="$4"
    local swap_mb="$5"

    echo ""
    echo -e "  ${BOLD}服务器环境检测${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo -e "  系统信息: ${BOLD}$os_name${NC}"
    echo -e "  内核版本: ${BOLD}$kernel${NC}"
    echo -e "  CPU 核数: ${BOLD}${cpu_cores}${NC}"
    echo -e "  物理内存: ${BOLD}$(format_mb "$mem_mb")${NC}"
    echo -e "  当前 Swap: ${BOLD}$(format_mb "$swap_mb")${NC}"
}

show_profile_apply_result() {
    local expected_workers="$1"
    local expected_node_build_memory_mb="$2"
    local expected_swap_mb="$3"
    local current_swap_mb
    current_swap_mb=$(get_total_swap_mb)

    echo ""
    echo -e "  ${BOLD}应用结果校验${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo -e "  Gunicorn workers: ${BOLD}${MIEMIE_WORKERS:-未设置}${NC}"
    echo -e "  Node 构建内存: ${BOLD}${NODE_BUILD_MEMORY_MB:-未设置}MB${NC}"
    echo -e "  当前 Swap: ${BOLD}$(format_mb "$current_swap_mb")${NC}"

    if [ "$MIEMIE_WORKERS" = "$expected_workers" ] && [ "$NODE_BUILD_MEMORY_MB" = "$expected_node_build_memory_mb" ]; then
        log_success "运行参数已写入配置并生效"
    else
        log_warn "检测到运行参数写入与预期不一致，请检查 $MIEMIE_CONF"
    fi

    if [ "$expected_swap_mb" -gt 0 ]; then
        if [ "$current_swap_mb" -ge "$expected_swap_mb" ]; then
            log_success "Swap 已达到推荐值"
        else
            log_warn "Swap 仍低于推荐值，可稍后再次进入维护菜单补充"
        fi
    fi
}

apply_swap_recommendation() {
    local current_swap_mb="$1"
    local recommended_swap_mb="$2"
    local swap_delta_mb=$(( recommended_swap_mb - current_swap_mb ))

    if [ "$(uname -s)" != "Linux" ] || [ "$recommended_swap_mb" -le 0 ] || [ "$swap_delta_mb" -le 0 ]; then
        return 0
    fi

    if [ -z "$SWAPFILE_PATH" ]; then
        SWAPFILE_PATH="/swapfile.miemie"
    fi

    if ! command -v mkswap &> /dev/null || ! command -v swapon &> /dev/null; then
        log_error "当前系统缺少 mkswap 或 swapon，无法自动创建 Swap"
        return 1
    fi

    if swapon --show=NAME --noheadings 2>/dev/null | grep -Fxq "$SWAPFILE_PATH"; then
        log_warn "检测到 $SWAPFILE_PATH 已作为活动 Swap 使用，暂不自动调整大小"
        return 1
    fi

    log_info "准备创建额外 Swap：$(format_mb "$swap_delta_mb") -> $SWAPFILE_PATH"

    if [ -e "$SWAPFILE_PATH" ]; then
        run_pkg_cmd rm -f "$SWAPFILE_PATH"
    fi

    if command -v fallocate &> /dev/null; then
        run_pkg_cmd fallocate -l "${swap_delta_mb}M" "$SWAPFILE_PATH"
    else
        run_pkg_cmd dd if=/dev/zero of="$SWAPFILE_PATH" bs=1M count="$swap_delta_mb" status=progress
    fi

    run_pkg_cmd chmod 600 "$SWAPFILE_PATH"
    run_pkg_cmd mkswap "$SWAPFILE_PATH"
    run_pkg_cmd swapon "$SWAPFILE_PATH"
    append_line_if_missing "/etc/fstab" "$SWAPFILE_PATH none swap sw 0 0"
}

maybe_offer_performance_profile() {
    local context="${1:-manual}"
    local force_prompt="${2:-false}"
    local os_name kernel cpu_cores mem_mb swap_mb signature
    local recommended_workers recommended_node_build_memory_mb recommended_swap_mb

    if ! is_interactive_shell; then
        return 0
    fi

    os_name=$(get_os_name)
    kernel=$(get_kernel_info)
    cpu_cores=$(get_cpu_cores)
    mem_mb=$(get_total_memory_mb)
    swap_mb=$(get_total_swap_mb)
    signature=$(build_perf_profile_signature "$kernel" "$mem_mb" "$cpu_cores")

    if [ "$force_prompt" != "true" ] && [ "$PERF_PROFILE_APPLIED" = "true" ] && [ "$PERF_PROFILE_SIGNATURE" = "$signature" ]; then
        return 0
    fi

    recommended_workers=$(recommend_gunicorn_workers "$mem_mb" "$cpu_cores")
    recommended_node_build_memory_mb=$(recommend_node_build_memory_mb "$mem_mb")
    recommended_swap_mb=$(recommend_swap_mb "$mem_mb" "$swap_mb")

    show_server_profile_summary "$os_name" "$kernel" "$cpu_cores" "$mem_mb" "$swap_mb"
    echo ""
    echo -e "  ${BOLD}推荐配置${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo -e "  Gunicorn workers: ${BOLD}${recommended_workers}${NC}"
    echo -e "  Node 构建内存上限: ${BOLD}${recommended_node_build_memory_mb}MB${NC}"
    if [ "$recommended_swap_mb" -gt 0 ]; then
        echo -e "  Swap 建议: ${BOLD}至少 $(format_mb "$recommended_swap_mb")${NC}"
        echo -e "  ${DIM}小内存服务器推荐开启额外 Swap，可降低 build / 重启时卡死概率${NC}"
    else
        echo -e "  Swap 建议: ${DIM}当前无需额外创建${NC}"
    fi
    echo ""

    if [ "$context" = "install" ]; then
        echo -e "  ${DIM}这是首次安装/维护阶段的推荐，优先兼顾性能和稳定性。${NC}"
    elif [ "$context" = "prod_start" ]; then
        echo -e "  ${DIM}这是生产模式启动前的推荐，避免重启或构建时把小机器打满。${NC}"
    fi
    echo ""

    read -p "  是否应用推荐的运行配置？[Y/n]: " apply_choice
    if [[ "$apply_choice" =~ ^[Nn]$ ]]; then
        log_info "已跳过自动优化配置"
        return 0
    fi

    MIEMIE_WORKERS="$recommended_workers"
    NODE_BUILD_MEMORY_MB="$recommended_node_build_memory_mb"
    PERF_PROFILE_APPLIED="true"
    PERF_PROFILE_SIGNATURE="$signature"
    save_config

    if [ "$recommended_swap_mb" -gt 0 ] && [ "$swap_mb" -lt "$recommended_swap_mb" ]; then
        echo ""
        read -p "  检测到内存较小，是否立即创建额外 Swap？[y/N]: " swap_choice
        if [[ "$swap_choice" =~ ^[Yy]$ ]]; then
            apply_swap_recommendation "$swap_mb" "$recommended_swap_mb" || log_warn "创建 Swap 失败，请按提示手动处理"
        else
            log_info "已跳过 Swap 创建"
        fi
    fi

    show_profile_apply_result "$recommended_workers" "$recommended_node_build_memory_mb" "$recommended_swap_mb"
}

# 初始加载配置
load_config

# ======================
# 服务状态检查
# ======================

is_backend_running() {
    screen -list 2>/dev/null | grep -q "$BACKEND_SESSION"
}

is_frontend_running() {
    screen -list 2>/dev/null | grep -q "$FRONTEND_SESSION"
}

# 检查端口是否被占用，返回占用进程的 PID
get_port_pid() {
    local port=$1
    lsof -ti :$port 2>/dev/null | head -1
}

# 检查端口并处理冲突
check_port_and_handle() {
    local port=$1
    local service_name=$2
    local pids=$(lsof -ti :$port 2>/dev/null)
    
    if [ -n "$pids" ]; then
        log_warn "端口 $port 已被占用"
        echo ""
        echo "占用进程:"
        lsof -i :$port 2>/dev/null | head -5
        echo ""
        echo "请选择操作:"
        echo "  1) 终止占用进程并继续启动"
        echo "  2) 取消启动"
        echo ""
        read -p "请选择 [1/2]: " choice
        
        case "$choice" in
            1)
                log_info "终止占用端口 $port 的进程..."
                for pid in $pids; do
                    kill $pid 2>/dev/null && log_info "已终止进程 PID: $pid"
                done
                sleep 1
                # 再次检查
                if [ -n "$(lsof -ti :$port 2>/dev/null)" ]; then
                    log_warn "进程未能正常终止，尝试强制终止..."
                    for pid in $pids; do
                        kill -9 $pid 2>/dev/null
                    done
                    sleep 1
                fi
                return 0
                ;;
            2|*)
                log_info "启动已取消"
                return 1
                ;;
        esac
    fi
    return 0
}

# ======================
# 服务启动
# ======================

start_backend() {
    if is_backend_running; then
        log_warn "后端服务已在运行"
        return 0
    fi

    check_lsof
    check_ffmpeg
    
    # 检查端口是否被占用
    if ! check_port_and_handle $BACKEND_PORT "后端"; then
        return 1
    fi
    
    # 确保依赖已安装
    if ! backend_deps_installed; then
        install_backend_deps
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 清空旧日志（避免混淆）
    > "$BACKEND_LOG"
    
    log_info "启动后端服务 (模式: $RUN_MODE)..."
    if [ "$RUN_MODE" = "prod" ]; then
        local worker_count
        worker_count="${MIEMIE_WORKERS:-$(get_default_gunicorn_workers)}"

        if ! backend_prod_deps_installed; then
            log_info "检测到生产模式依赖缺失，正在安装 gunicorn / slowapi ..."
            "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q
        fi
        log_info "生产模式 Gunicorn workers: $worker_count"
        screen -dmS "$BACKEND_SESSION" bash -c "
            cd '$BACKEND_DIR'
            source '$VENV_DIR/bin/activate'
            export MIEMIE_SERVE_FRONTEND=true
            export MIEMIE_FRONTEND_PORT=$FRONTEND_PORT
            export MIEMIE_WORKERS=$worker_count
            gunicorn app.main:app \
                -w \$MIEMIE_WORKERS \
                -k uvicorn.workers.UvicornWorker \
                --bind $LISTEN_HOST:$BACKEND_PORT \
                --timeout 300 \
                --graceful-timeout 30 \
                --access-logfile '$BACKEND_LOG' \
                --error-logfile '$BACKEND_LOG' \
                2>&1 | tee -a '$BACKEND_LOG'
        "
    else
        screen -dmS "$BACKEND_SESSION" bash -c "
            cd '$BACKEND_DIR'
            source '$VENV_DIR/bin/activate'
            export MIEMIE_FRONTEND_PORT=$FRONTEND_PORT
            uvicorn app.main:app --reload --host $LISTEN_HOST --port $BACKEND_PORT 2>&1 | tee -a '$BACKEND_LOG'
        "
    fi
    
    sleep 2
    local display_host
    display_host=$(get_display_host)
    if is_backend_running; then
        log_success "后端服务已启动 (http://${display_host}:$BACKEND_PORT)"
    else
        log_error "后端服务启动失败，请查看日志: $BACKEND_LOG"
        return 1
    fi
}

build_frontend() {
    # 确保依赖已安装
    if ! frontend_deps_installed; then
        install_frontend_deps
    fi

    log_info "构建前端生产版本..."
    log_info "提示：Vite 构建在 'transforming...' 后可能静默几十秒到几分钟，低配服务器上属于正常现象"
    mkdir -p "$LOG_DIR"
    > "$FRONTEND_LOG"
    cd "$FRONTEND_DIR"
    local build_memory_mb
    build_memory_mb="${NODE_BUILD_MEMORY_MB:-$(recommend_node_build_memory_mb "$(get_total_memory_mb)")}"
    log_info "前端构建 Node 内存上限: ${build_memory_mb}MB"
    export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=${build_memory_mb}}"
    set +e
    npm run build 2>&1 | tee -a "$FRONTEND_LOG"
    local build_exit=${PIPESTATUS[0]}
    set -e
    cd "$PROJECT_DIR"
    if [ $build_exit -ne 0 ]; then
        log_error "前端构建失败（退出码: $build_exit），请检查日志"
        return 1
    fi
    log_success "前端构建完成"
}

start_frontend() {
    # 生产模式下不需要独立前端服务器（由后端提供）
    if [ "$RUN_MODE" = "prod" ]; then
        build_frontend || return 1
        local display_host
        display_host=$(get_display_host)
        log_success "前端已构建，由后端统一服务 (http://${display_host}:$BACKEND_PORT)"
        return 0
    fi

    if is_frontend_running; then
        log_warn "前端服务已在运行"
        return 0
    fi
    
    # 检查端口是否被占用
    if ! check_port_and_handle $FRONTEND_PORT "前端"; then
        return 1
    fi
    
    # 确保依赖已安装
    if ! frontend_deps_installed; then
        install_frontend_deps
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 清空旧日志（避免混淆）
    > "$FRONTEND_LOG"
    
    log_info "启动前端开发服务器..."
    local host_flag=""
    if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
        host_flag="--host 0.0.0.0"
    else
        host_flag="--host 127.0.0.1"
    fi
    screen -dmS "$FRONTEND_SESSION" bash -c "
        cd '$FRONTEND_DIR'
        npm run dev -- $host_flag --port $FRONTEND_PORT 2>&1 | tee -a '$FRONTEND_LOG'
    "
    
    sleep 3
    local display_host
    display_host=$(get_display_host)
    if is_frontend_running; then
        log_success "前端服务已启动 (http://${display_host}:$FRONTEND_PORT)"
    else
        log_error "前端服务启动失败，请查看日志: $FRONTEND_LOG"
        return 1
    fi
}

start_all() {
    check_screen
    check_lsof
    log_info "启动 MieMie-Studio (模式: $RUN_MODE)..."
    echo ""
    if [ "$RUN_MODE" = "prod" ]; then
        maybe_offer_performance_profile "prod_start" "false"
        build_frontend || return 1
        start_backend || return 1
        local display_host
        display_host=$(get_display_host)
        log_success "前端已构建，由后端统一服务 (http://${display_host}:$BACKEND_PORT)"
    else
        start_backend || return 1
        start_frontend || return 1
    fi
    echo ""
    log_success "MieMie-Studio 启动完成!"
    echo ""

    local display_host
    display_host=$(get_display_host)
    local is_public="否"
    [ "$LISTEN_HOST" = "0.0.0.0" ] && is_public="是"

    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo -e "  公网访问: ${BOLD}${is_public}${NC}    监听地址: ${BOLD}${LISTEN_HOST}${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo -e "  访问地址:"
    if [ "$RUN_MODE" = "prod" ]; then
        echo -e "  ${BOLD}应用页面${NC}  http://${display_host}:$BACKEND_PORT"
    else
        echo -e "  ${BOLD}前端页面${NC}  http://${display_host}:$FRONTEND_PORT"
        echo -e "  ${BOLD}后端接口${NC}  http://${display_host}:$BACKEND_PORT"
        echo -e "  ${BOLD}API 文档${NC}  http://${display_host}:$BACKEND_PORT/docs"
    fi
    if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
        echo -e ""
        echo -e "  ${DIM}本机也可用: http://localhost:$BACKEND_PORT${NC}"
    fi
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
}

# ======================
# 服务停止
# ======================

# 终止指定端口的所有进程
kill_port_processes() {
    local port=$1
    local pids=$(lsof -ti :$port 2>/dev/null)
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            kill $pid 2>/dev/null
        done
        sleep 1
        # 检查是否还有残留进程
        pids=$(lsof -ti :$port 2>/dev/null)
        if [ -n "$pids" ]; then
            for pid in $pids; do
                kill -9 $pid 2>/dev/null
            done
        fi
    fi
}

stop_backend() {
    local was_running=false
    
    if is_backend_running; then
        was_running=true
        log_info "停止后端服务..."
        # 先发送 SIGTERM 给 screen 会话中的进程
        screen -S "$BACKEND_SESSION" -X stuff $'\003' 2>/dev/null  # 发送 Ctrl+C
        sleep 1
        screen -S "$BACKEND_SESSION" -X quit 2>/dev/null || true
    fi
    
    # 确保端口上的进程被终止
    if [ -n "$(lsof -ti :$BACKEND_PORT 2>/dev/null)" ]; then
        log_info "清理残留的后端进程..."
        kill_port_processes $BACKEND_PORT
    fi
    
    if $was_running; then
        log_success "后端服务已停止"
    else
        log_info "后端服务未运行"
    fi
}

stop_frontend() {
    local was_running=false
    
    if is_frontend_running; then
        was_running=true
        log_info "停止前端服务..."
        # 先发送 SIGTERM 给 screen 会话中的进程
        screen -S "$FRONTEND_SESSION" -X stuff $'\003' 2>/dev/null  # 发送 Ctrl+C
        sleep 1
        screen -S "$FRONTEND_SESSION" -X quit 2>/dev/null || true
    fi
    
    # 确保端口上的进程被终止
    if [ -n "$(lsof -ti :$FRONTEND_PORT 2>/dev/null)" ]; then
        log_info "清理残留的前端进程..."
        kill_port_processes $FRONTEND_PORT
    fi
    
    if $was_running; then
        log_success "前端服务已停止"
    else
        log_info "前端服务未运行"
    fi
}

stop_all() {
    check_lsof
    log_info "停止 MieMie-Studio..."
    stop_backend
    stop_frontend
    log_success "MieMie-Studio 已停止"
}

# ======================
# 服务状态
# ======================

show_status() {
    check_lsof
    echo ""
    echo -e "  ${BOLD}服务状态${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo ""

    # 网络状态
    if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
        local server_ip
        server_ip=$(get_server_ip)
        echo -e "  公网访问    ${GREEN}● 已开启${NC}   IP: $server_ip"
    else
        echo -e "  公网访问    ${RED}○ 已关闭${NC}   仅本机可访问"
    fi
    echo -e "  Workers     ${CYAN}${MIEMIE_WORKERS:-自动}${NC}"
    echo -e "  构建内存    ${CYAN}${NODE_BUILD_MEMORY_MB:-自动}MB${NC}"
    
    # 后端状态
    local backend_port_pid=$(get_port_pid $BACKEND_PORT)
    if is_backend_running; then
        echo -e "  后端服务    ${GREEN}● 运行中${NC}   端口 $BACKEND_PORT"
    elif [ -n "$backend_port_pid" ]; then
        echo -e "  后端服务    ${YELLOW}▲ 异常${NC}     screen 已退出但端口 $BACKEND_PORT 仍被 PID $backend_port_pid 占用"
    else
        echo -e "  后端服务    ${RED}○ 未运行${NC}"
    fi
    
    # 前端状态
    if [ "$RUN_MODE" = "prod" ]; then
        if [ -d "$FRONTEND_DIR/dist" ] && [ -f "$FRONTEND_DIR/dist/index.html" ]; then
            echo -e "  前端服务    ${GREEN}● 已构建${NC}   由后端统一服务"
        else
            echo -e "  前端服务    ${YELLOW}○ 未构建${NC}   需要先启动生产模式"
        fi
    else
        local frontend_port_pid=$(get_port_pid $FRONTEND_PORT)
        if is_frontend_running; then
            echo -e "  前端服务    ${GREEN}● 运行中${NC}   端口 $FRONTEND_PORT"
        elif [ -n "$frontend_port_pid" ]; then
            echo -e "  前端服务    ${YELLOW}▲ 异常${NC}     screen 已退出但端口 $FRONTEND_PORT 仍被 PID $frontend_port_pid 占用"
        else
            echo -e "  前端服务    ${RED}○ 未运行${NC}"
        fi
    fi
    
    echo ""
    echo -e "  ${BOLD}环境检查${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo ""
    
    if venv_exists; then
        echo -e "  Python 环境   ${GREEN}✓ 已就绪${NC}"
    else
        echo -e "  Python 环境   ${YELLOW}✗ 未创建${NC}  ${DIM}请先运行安装依赖${NC}"
    fi
    
    if backend_deps_installed; then
        echo -e "  后端依赖      ${GREEN}✓ 已安装${NC}"
    else
        echo -e "  后端依赖      ${YELLOW}✗ 未安装${NC}  ${DIM}请先运行安装依赖${NC}"
    fi
    
    if frontend_deps_installed; then
        echo -e "  前端依赖      ${GREEN}✓ 已安装${NC}"
    else
        echo -e "  前端依赖      ${YELLOW}✗ 未安装${NC}  ${DIM}请先运行安装依赖${NC}"
    fi
    
    # 自动更新状态
    echo ""
    if crontab -l 2>/dev/null | grep -q "$AUTO_UPDATE_CRON_TAG"; then
        echo -e "  自动更新      ${GREEN}✓ 已开启${NC}  ${DIM}每日 03:00${NC}"
    else
        echo -e "  自动更新      ${DIM}未开启${NC}"
    fi
    
    echo ""
}

# ======================
# 日志查看
# ======================

show_logs() {
    local service="${1:-all}"
    
    case "$service" in
        backend)
            if [ -f "$BACKEND_LOG" ]; then
                tail -f "$BACKEND_LOG"
            else
                log_warn "后端日志文件不存在"
            fi
            ;;
        frontend)
            if [ -f "$FRONTEND_LOG" ]; then
                tail -f "$FRONTEND_LOG"
            else
                log_warn "前端日志文件不存在"
            fi
            ;;
        all)
            echo "使用 Ctrl+C 退出日志查看"
            echo ""
            echo "--- 连接到后端 screen 会话 (按 Ctrl+A, D 分离) ---"
            if is_backend_running; then
                screen -r "$BACKEND_SESSION"
            else
                log_warn "后端未运行"
            fi
            ;;
        *)
            log_error "未知服务: $service"
            echo "用法: ./run.sh logs [backend|frontend|all]"
            ;;
    esac
}

# ======================
# 更新项目
# ======================

update_project() {
    local is_auto=false
    for arg in "$@"; do
        if [ "$arg" = "--auto" ]; then
            is_auto=true
        fi
    done

    log_info "检查更新... $(date '+%Y-%m-%d %H:%M:%S')"

    # 备份用户数据
    mkdir -p "$BACKUP_DIR"
    if [ -d "$PROJECT_DIR/backend/data" ]; then
        local backup_name="pre_update_$(date +%Y%m%d_%H%M%S)"
        cp -r "$PROJECT_DIR/backend/data" "$BACKUP_DIR/$backup_name"
        # 同时备份运行配置
        if [ -f "$MIEMIE_CONF" ]; then
            cp "$MIEMIE_CONF" "$BACKUP_DIR/$backup_name/.miemie.conf"
        fi
        log_info "数据已备份: $BACKUP_DIR/$backup_name"
        # 保留最近 10 个备份
        ls -dt "$BACKUP_DIR"/pre_update_* 2>/dev/null | tail -n +11 | xargs rm -rf 2>/dev/null
    fi

    # 检查是否有未提交的更改
    if ! git diff --quiet 2>/dev/null; then
        if $is_auto; then
            log_info "自动更新：暂存本地更改..."
            git stash
        else
            log_warn "检测到本地有未提交的更改"
            echo ""
            echo "本地修改的文件:"
            git diff --name-only
            echo ""
            read -p "是否暂存本地更改并继续更新? (y/N): " confirm
            if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
                log_info "更新已取消"
                return 0
            fi
            log_info "暂存本地更改..."
            git stash
        fi
    fi

    log_info "获取最新代码..."
    git fetch origin

    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master)

    if [ "$LOCAL" = "$REMOTE" ]; then
        log_success "已是最新版本"
        git stash pop 2>/dev/null || true
        return 0
    fi

    log_info "发现新版本，更新内容:"
    git log --oneline HEAD..origin/main 2>/dev/null || git log --oneline HEAD..origin/master
    echo ""

    log_info "正在更新..."
    git pull origin main 2>/dev/null || git pull origin master

    if git stash list | grep -q "stash@{0}"; then
        log_info "恢复本地更改..."
        git stash pop || {
            log_warn "自动合并失败，请手动解决冲突"
            log_info "使用 'git stash pop' 查看暂存的更改"
        }
    fi

    log_info "检查依赖更新..."
    if git diff HEAD~1 --name-only | grep -q "requirements.txt"; then
        log_info "检测到 Python 依赖变化，更新中..."
        "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    fi
    if git diff HEAD~1 --name-only | grep -q "frontend/package.json"; then
        log_info "检测到前端依赖变化，更新中..."
        cd "$FRONTEND_DIR"
        npm install
        cd "$PROJECT_DIR"
    fi

    log_success "更新完成！"

    # 自动模式下自动重启服务
    if $is_auto; then
        if is_backend_running || is_frontend_running; then
            log_info "自动更新：重启服务..."
            stop_all
            sleep 2
            start_all
        fi
    else
        echo ""
        log_info "如果服务正在运行，建议重启以应用更新："
        echo "  ./run.sh restart"
    fi
}

# ======================
# 自动更新管理
# ======================

AUTO_UPDATE_CRON_TAG="miemie-studio-auto-update"
UPDATE_LOG="$LOG_DIR/update.log"
BACKUP_DIR="$PROJECT_DIR/backups"

auto_update_manage() {
    local action="${1:-status}"

    case "$action" in
        enable)
            auto_update_enable
            ;;
        disable)
            auto_update_disable
            ;;
        status)
            auto_update_status
            ;;
        *)
            log_error "未知操作: $action"
            echo "用法: ./run.sh auto-update [enable|disable|status]"
            ;;
    esac
}

auto_update_enable() {
    local cron_cmd="0 3 * * * cd '$PROJECT_DIR' && '$PROJECT_DIR/run.sh' update --auto >> '$UPDATE_LOG' 2>&1"

    # 检查是否已存在
    if crontab -l 2>/dev/null | grep -q "$AUTO_UPDATE_CRON_TAG"; then
        log_warn "自动更新已启用"
        return 0
    fi

    # 添加 cron 任务
    (crontab -l 2>/dev/null; echo "$cron_cmd # $AUTO_UPDATE_CRON_TAG") | crontab -
    mkdir -p "$LOG_DIR"
    log_success "自动更新已启用（每日凌晨 3:00 执行）"
    echo "  更新日志: $UPDATE_LOG"
}

auto_update_disable() {
    if ! crontab -l 2>/dev/null | grep -q "$AUTO_UPDATE_CRON_TAG"; then
        log_info "自动更新未启用"
        return 0
    fi

    crontab -l 2>/dev/null | grep -v "$AUTO_UPDATE_CRON_TAG" | crontab -
    log_success "自动更新已禁用"
}

auto_update_status() {
    echo ""
    echo "========== 自动更新状态 =========="
    echo ""
    if crontab -l 2>/dev/null | grep -q "$AUTO_UPDATE_CRON_TAG"; then
        echo -e "  状态: ${GREEN}已启用${NC} (每日 03:00)"
        echo "  Cron: $(crontab -l 2>/dev/null | grep "$AUTO_UPDATE_CRON_TAG" | sed "s/ # $AUTO_UPDATE_CRON_TAG//")"
    else
        echo -e "  状态: ${RED}未启用${NC}"
    fi
    if [ -f "$UPDATE_LOG" ]; then
        echo ""
        echo "  最近一次更新日志:"
        tail -5 "$UPDATE_LOG" | sed 's/^/    /'
    fi
    echo ""
    echo "==================================="
}

# ======================
# 版本回滚
# ======================

rollback_version() {
    if [ ! -d ".git" ]; then
        log_error "非 Git 仓库，无法回滚"
        return 1
    fi

    # 获取最近的提交列表
    echo ""
    echo "最近 10 次提交:"
    echo ""
    git log --oneline -10
    echo ""

    # 获取上一个版本
    local prev_commit
    prev_commit=$(git rev-parse HEAD~1 2>/dev/null)
    if [ -z "$prev_commit" ]; then
        log_error "无法获取上一个版本"
        return 1
    fi

    local prev_short
    prev_short=$(git rev-parse --short HEAD~1)
    local curr_short
    curr_short=$(git rev-parse --short HEAD)

    echo "当前版本: $curr_short"
    echo "回滚目标: $prev_short"
    echo ""
    read -p "确认回滚到 $prev_short ? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "回滚已取消"
        return 0
    fi

    # 备份数据
    log_info "备份用户数据..."
    mkdir -p "$BACKUP_DIR"
    local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
    if [ -d "$PROJECT_DIR/backend/data" ]; then
        cp -r "$PROJECT_DIR/backend/data" "$BACKUP_DIR/$backup_name"
        if [ -f "$MIEMIE_CONF" ]; then
            cp "$MIEMIE_CONF" "$BACKUP_DIR/$backup_name/.miemie.conf"
        fi
        log_success "数据已备份到 $BACKUP_DIR/$backup_name"
    fi

    log_info "回滚到 $prev_short ..."
    git checkout "$prev_commit" -- .
    git checkout HEAD -- backend/data 2>/dev/null || true

    log_success "回滚完成！建议重启服务: ./run.sh restart"
}

# ======================
# 清理项目
# ======================

run_tests() {
    log_info "运行后端测试..."
    PYTHON=$(check_python)
    if [ -z "$PYTHON" ]; then
        log_error "未找到 Python 环境"
        return 1
    fi

    # 激活虚拟环境
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    fi

    # 检查 pytest 是否安装
    if ! "$PYTHON" -m pytest --version > /dev/null 2>&1; then
        log_info "安装 pytest..."
        "$PYTHON" -m pip install pytest pytest-asyncio -q
    fi

    cd "$BACKEND_DIR"
    "$PYTHON" -m pytest tests/ -v
    local exit_code=$?
    cd "$PROJECT_DIR"

    if [ $exit_code -eq 0 ]; then
        log_success "所有测试通过"
    else
        log_error "部分测试失败 (exit code: $exit_code)"
    fi
    return $exit_code
}

clean_project() {
    echo ""
    echo -e "  ${BOLD}清理与重置${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC})  清理日志文件        ${DIM}— 删除运行日志，释放磁盘空间${NC}"
    echo -e "  ${GREEN}2${NC})  清理 Python 缓存    ${DIM}— 删除 __pycache__，排查导入问题${NC}"
    echo -e "  ${GREEN}3${NC})  重置前端依赖        ${DIM}— 删除 node_modules 并重新安装${NC}"
    echo -e "  ${GREEN}4${NC})  重置后端依赖        ${DIM}— 删除虚拟环境并重新创建${NC}"
    echo -e "  ${YELLOW}5${NC})  全部清理并重新安装  ${DIM}— 以上全部执行，耗时较长${NC}"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-5]: " choice
    
    case "$choice" in
        1)
            log_info "清理日志文件..."
            rm -rf "$LOG_DIR"/*.log 2>/dev/null
            rm -rf "$BACKEND_DIR/logs"/*.log 2>/dev/null
            log_success "日志已清理"
            ;;
        2)
            log_info "清理 Python 缓存..."
            find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
            find "$PROJECT_DIR" -type f -name "*.pyc" -delete 2>/dev/null
            log_success "缓存已清理"
            ;;
        3)
            log_info "重置前端依赖..."
            rm -rf "$FRONTEND_DIR/node_modules"
            cd "$FRONTEND_DIR"
            npm install
            cd "$PROJECT_DIR"
            log_success "前端依赖已重置"
            ;;
        4)
            log_info "重置后端依赖..."
            rm -rf "$VENV_DIR"
            create_venv
            install_backend_deps
            log_success "后端依赖已重置"
            ;;
        5)
            log_info "全部清理并重新安装..."
            rm -rf "$LOG_DIR"/*.log 2>/dev/null
            rm -rf "$BACKEND_DIR/logs"/*.log 2>/dev/null
            find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
            rm -rf "$FRONTEND_DIR/node_modules"
            rm -rf "$VENV_DIR"
            install_all_deps
            log_success "清理完成，依赖已重新安装"
            ;;
        0|*)
            ;;
    esac
}

# ======================
# 显示版本信息
# ======================

show_version() {
    echo ""
    echo -e "  ${BOLD}MieMie-Studio${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo ""
    
    if [ -d ".git" ]; then
        local commit branch date
        commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        branch=$(git branch --show-current 2>/dev/null || echo "unknown")
        date=$(git log -1 --format=%cd --date=short 2>/dev/null || echo "unknown")
        echo -e "  版本      ${CYAN}$commit${NC} (${branch})"
        echo -e "  更新日期  $date"
    else
        echo "  版本      未知（非 Git 仓库）"
    fi
    
    echo ""
    echo -e "  项目地址  ${BLUE}https://github.com/Zijian-Yang/MieMie-Studio${NC}"
    echo -e "  许可证    GPL v3"
    echo ""
}

# ======================
# 连接到 screen 会话
# ======================

attach_session() {
    local service="${1:-backend}"
    
    case "$service" in
        backend)
            if is_backend_running; then
                log_info "连接到后端会话 (按 Ctrl+A, D 分离)"
                screen -r "$BACKEND_SESSION"
            else
                log_warn "后端未运行"
            fi
            ;;
        frontend)
            if is_frontend_running; then
                log_info "连接到前端会话 (按 Ctrl+A, D 分离)"
                screen -r "$FRONTEND_SESSION"
            else
                log_warn "前端未运行"
            fi
            ;;
        *)
            log_error "未知服务: $service"
            echo "用法: ./run.sh attach [backend|frontend]"
            ;;
    esac
}

# ======================
# 交互式菜单系统
# ======================

print_header() {
    clear
    echo ""
    echo -e "${BOLD}${CYAN}  ╔═══════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}  ║         MieMie-Studio  控制面板              ║${NC}"
    echo -e "${BOLD}${CYAN}  ╚═══════════════════════════════════════════════╝${NC}"
    echo ""

    # 状态栏
    local be_status fe_status
    if is_backend_running; then
        be_status="${GREEN}● 运行中${NC}"
    else
        be_status="${RED}● 未运行${NC}"
    fi
    if [ "$RUN_MODE" = "prod" ]; then
        if [ -d "$FRONTEND_DIR/dist" ] && [ -f "$FRONTEND_DIR/dist/index.html" ]; then
            fe_status="${GREEN}● 已构建${NC}"
        else
            fe_status="${YELLOW}○ 未构建${NC}"
        fi
    else
        if is_frontend_running; then
            fe_status="${GREEN}● 运行中${NC}"
        else
            fe_status="${RED}● 未运行${NC}"
        fi
    fi
    echo -e "  后端 $be_status    前端 $fe_status    模式: ${YELLOW}$RUN_MODE${NC}"
    echo ""
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo ""
}

# ======================
# 网络访问设置
# ======================

prompt_restart_if_running() {
    if is_backend_running || is_frontend_running; then
        log_warn "设置将在下次启动/重启服务后生效"
        echo ""
        read -p "  是否立即重启服务？[y/N]: " restart_choice
        if [[ "$restart_choice" =~ ^[Yy]$ ]]; then
            echo ""
            stop_all
            sleep 2
            start_all
        fi
    fi
}

menu_network() {
    print_header

    local current_status
    if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
        current_status="${GREEN}已开启${NC}"
    else
        current_status="${RED}已关闭${NC}"
    fi

    local server_ip
    server_ip=$(get_server_ip)

    echo -e "  ${BOLD}网络访问设置${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  公网访问:  $current_status"
    echo -e "  监听地址:  ${BOLD}$LISTEN_HOST${NC}"
    echo -e "  本机 IP:   ${BOLD}$server_ip${NC}"
    echo -e "  后端端口:  ${BOLD}$BACKEND_PORT${NC}"
    echo -e "  前端端口:  ${BOLD}$FRONTEND_PORT${NC}"
    if [ -n "$ALLOWED_DOMAINS" ]; then
        echo -e "  绑定域名:  ${BOLD}$ALLOWED_DOMAINS${NC}"
    else
        echo -e "  绑定域名:  ${DIM}无（仅 IP 访问）${NC}"
    fi
    echo ""
    echo -e "  ${GREEN}1${NC})  开启公网访问    ${DIM}— 监听 0.0.0.0，允许外部 IP 连接${NC}"
    echo -e "  ${GREEN}2${NC})  关闭公网访问    ${DIM}— 监听 127.0.0.1，仅本机可访问${NC}"
    echo -e "  ${GREEN}3${NC})  绑定域名        ${DIM}— 通过 Nginx 反代域名访问时必须设置${NC}"
    echo -e "  ${GREEN}4${NC})  清除域名        ${DIM}— 移除已绑定的域名${NC}"
    echo -e "  ${GREEN}5${NC})  修改端口        ${DIM}— 自定义前端/后端服务端口${NC}"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-5]: " choice

    case "$choice" in
        1)
            LISTEN_HOST="0.0.0.0"
            save_config
            echo ""
            log_success "公网访问已开启"
            log_info "监听地址: 0.0.0.0"
            log_info "访问链接: http://${server_ip}:$BACKEND_PORT"
            echo ""
            prompt_restart_if_running
            wait_key
            ;;
        2)
            LISTEN_HOST="127.0.0.1"
            save_config
            echo ""
            log_success "公网访问已关闭"
            log_info "监听地址: 127.0.0.1 (仅本机)"
            echo ""
            prompt_restart_if_running
            wait_key
            ;;
        3)
            echo ""
            echo -e "  ${DIM}如果你通过 Nginx 反向代理域名来访问本平台，需要在此绑定域名。${NC}"
            echo -e "  ${DIM}多个域名用逗号分隔，例如: studio.example.com,app.example.com${NC}"
            echo ""
            if [ -n "$ALLOWED_DOMAINS" ]; then
                echo -e "  当前域名: ${BOLD}$ALLOWED_DOMAINS${NC}"
                echo ""
            fi
            read -p "  请输入域名: " input_domains

            if [ -z "$input_domains" ]; then
                log_warn "未输入域名，操作取消"
            else
                # 去空格
                input_domains=$(echo "$input_domains" | tr -d ' ')
                ALLOWED_DOMAINS="$input_domains"
                save_config
                echo ""
                log_success "域名已绑定: $ALLOWED_DOMAINS"

                # 同时自动开启公网访问
                if [ "$LISTEN_HOST" != "0.0.0.0" ]; then
                    LISTEN_HOST="0.0.0.0"
                    save_config
                    log_info "已自动开启公网访问"
                fi

                echo ""
                local first_domain
                first_domain=$(echo "$ALLOWED_DOMAINS" | cut -d',' -f1)
                log_info "访问链接: http://${first_domain}"
                echo ""
                prompt_restart_if_running
            fi
            wait_key
            ;;
        4)
            ALLOWED_DOMAINS=""
            save_config
            echo ""
            log_success "已清除绑定域名"
            echo ""
            prompt_restart_if_running
            wait_key
            ;;
        5)
            echo ""
            echo -e "  当前端口:  后端 ${BOLD}$BACKEND_PORT${NC}  /  前端 ${BOLD}$FRONTEND_PORT${NC}"
            echo -e "  ${DIM}直接回车保持当前值不变${NC}"
            echo ""
            read -p "  后端端口 [$BACKEND_PORT]: " input_backend_port
            read -p "  前端端口 [$FRONTEND_PORT]: " input_frontend_port

            local changed=false
            if [ -n "$input_backend_port" ]; then
                if [[ "$input_backend_port" =~ ^[0-9]+$ ]] && [ "$input_backend_port" -ge 1024 ] && [ "$input_backend_port" -le 65535 ]; then
                    BACKEND_PORT="$input_backend_port"
                    changed=true
                else
                    log_error "无效端口号（需 1024-65535）"
                fi
            fi
            if [ -n "$input_frontend_port" ]; then
                if [[ "$input_frontend_port" =~ ^[0-9]+$ ]] && [ "$input_frontend_port" -ge 1024 ] && [ "$input_frontend_port" -le 65535 ]; then
                    FRONTEND_PORT="$input_frontend_port"
                    changed=true
                else
                    log_error "无效端口号（需 1024-65535）"
                fi
            fi
            if [ "$BACKEND_PORT" = "$FRONTEND_PORT" ]; then
                log_error "前端和后端端口不能相同"
            elif [ "$changed" = true ]; then
                save_config
                echo ""
                log_success "端口已更新:  后端 $BACKEND_PORT  /  前端 $FRONTEND_PORT"
                echo ""
                prompt_restart_if_running
            fi
            wait_key
            ;;
        *) ;;
    esac
}

wait_key() {
    echo ""
    read -p "  按回车键返回主菜单..." _
}

menu_main() {
    while true; do
        print_header

        echo -e "  ${BOLD}请输入编号选择操作:${NC}"
        echo ""
        echo -e "  ${GREEN}1${NC})  启动服务        ${DIM}— 启动前后端，首次使用选这个${NC}"
        echo -e "  ${GREEN}2${NC})  停止服务        ${DIM}— 关闭所有正在运行的服务${NC}"
        echo -e "  ${GREEN}3${NC})  重启服务        ${DIM}— 先停止再启动，更新代码后需要重启${NC}"
        echo -e "  ${GREEN}4${NC})  查看状态        ${DIM}— 检查服务和环境是否正常${NC}"
        echo -e "  ${GREEN}5${NC})  查看日志        ${DIM}— 查看后端或前端运行日志${NC}"
        echo ""
        echo -e "  ${BLUE}6${NC})  更新到最新版本  ${DIM}— 从 GitHub 拉取作者发布的最新代码${NC}"
        echo -e "  ${BLUE}7${NC})  自动更新设置    ${DIM}— 开启后每天自动检查并更新${NC}"
        echo -e "  ${BLUE}8${NC})  版本回滚        ${DIM}— 更新后遇到问题？回退到上一个版本${NC}"
        echo ""
        echo -e "  ${YELLOW}9${NC})  安装/维护       ${DIM}— 安装依赖、清理缓存、重置环境${NC}"
        echo -e "  ${YELLOW}n${NC})  网络设置        ${DIM}— 开启/关闭公网访问，查看访问链接${NC}"
        echo -e "  ${YELLOW}v${NC})  版本信息        ${DIM}— 查看当前版本号和项目信息${NC}"
        echo -e "  ${RED}0${NC})  退出"
        echo ""
        read -p "  请输入 [0-9/n/v]: " choice

        case "$choice" in
            1) menu_start ;;
            2)
                echo ""
                stop_all
                wait_key
                ;;
            3) menu_restart ;;
            4)
                show_status
                wait_key
                ;;
            5) menu_logs ;;
            6)
                echo ""
                update_project
                wait_key
                ;;
            7) menu_auto_update ;;
            8)
                rollback_version
                wait_key
                ;;
            9) menu_maintenance ;;
            n|N) menu_network ;;
            v|V)
                show_version
                wait_key
                ;;
            0|q|Q)
                echo ""
                echo -e "  ${DIM}再见！${NC}"
                echo ""
                exit 0
                ;;
            *)
                ;;
        esac
    done
}

menu_start() {
    print_header
    echo -e "  ${BOLD}选择启动模式:${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC})  开发模式  ${DIM}— 日常使用推荐，支持代码热更新${NC}"
    echo -e "  ${GREEN}2${NC})  生产模式  ${DIM}— 部署到服务器时使用，性能更好更稳定${NC}"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-2]: " choice

    case "$choice" in
        1)
            RUN_MODE="dev"
            echo ""
            start_all
            wait_key
            ;;
        2)
            RUN_MODE="prod"
            echo ""
            start_all
            wait_key
            ;;
        *) ;;
    esac
}

menu_restart() {
    print_header
    echo -e "  ${BOLD}选择重启模式:${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC})  开发模式重启"
    echo -e "  ${GREEN}2${NC})  生产模式重启"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-2]: " choice

    case "$choice" in
        1)
            RUN_MODE="dev"
            echo ""
            stop_all
            sleep 2
            start_all
            wait_key
            ;;
        2)
            RUN_MODE="prod"
            echo ""
            stop_all
            sleep 2
            start_all
            wait_key
            ;;
        *) ;;
    esac
}

menu_logs() {
    print_header
    echo -e "  ${BOLD}查看哪个服务的日志？${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC})  后端日志    ${DIM}— Python/FastAPI 服务的输出${NC}"
    echo -e "  ${GREEN}2${NC})  前端日志    ${DIM}— React/Vite 开发服务器的输出${NC}"
    echo -e "  ${GREEN}3${NC})  连接后端终端  ${DIM}— 实时查看后端进程（按 Ctrl+A 再按 D 退出）${NC}"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-3]: " choice

    case "$choice" in
        1) show_logs "backend" ;;
        2) show_logs "frontend" ;;
        3) attach_session "backend" ;;
        *) ;;
    esac
}

menu_auto_update() {
    print_header
    echo -e "  ${BOLD}自动更新管理${NC}"
    echo -e "  ${DIM}开启后，系统每天凌晨 3:00 自动检查 GitHub 上的新版本。${NC}"
    echo -e "  ${DIM}更新过程会自动备份你的数据，不会丢失任何内容。${NC}"
    echo ""

    if crontab -l 2>/dev/null | grep -q "$AUTO_UPDATE_CRON_TAG"; then
        echo -e "  当前状态: ${GREEN}已开启${NC}"
    else
        echo -e "  当前状态: ${YELLOW}未开启${NC}"
    fi
    echo ""
    echo -e "  ${GREEN}1${NC})  开启自动更新"
    echo -e "  ${GREEN}2${NC})  关闭自动更新"
    echo -e "  ${GREEN}3${NC})  查看更新日志"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-3]: " choice

    case "$choice" in
        1)
            echo ""
            auto_update_enable
            wait_key
            ;;
        2)
            echo ""
            auto_update_disable
            wait_key
            ;;
        3)
            echo ""
            if [ -f "$UPDATE_LOG" ]; then
                echo "  最近更新日志（最后 20 行）:"
                echo ""
                tail -20 "$UPDATE_LOG" | sed 's/^/    /'
            else
                log_info "暂无更新日志"
            fi
            wait_key
            ;;
        *) ;;
    esac
}

menu_maintenance() {
    print_header
    echo -e "  ${BOLD}安装与维护${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC})  安装全部依赖    ${DIM}— 首次使用或依赖缺失时选择${NC}"
    echo -e "  ${GREEN}2${NC})  运行后端测试    ${DIM}— 运行 pytest 自动化测试${NC}"
    echo -e "  ${GREEN}3${NC})  清理与重置      ${DIM}— 清理日志、缓存，或重新安装依赖${NC}"
    echo -e "  ${GREEN}4${NC})  服务器优化建议  ${DIM}— 自动检测内核/内存并推荐配置${NC}"
    echo -e "  ${RED}0${NC})  返回"
    echo ""
    read -p "  请选择 [0-4]: " choice

    case "$choice" in
        1)
            echo ""
            install_all_deps
            wait_key
            ;;
        2)
            echo ""
            run_tests
            wait_key
            ;;
        3)
            clean_project
            wait_key
            ;;
        4)
            echo ""
            maybe_offer_performance_profile "manual" "true"
            wait_key
            ;;
        *) ;;
    esac
}

# ======================
# 命令行帮助（非交互模式）
# ======================

show_help() {
    echo ""
    echo "MieMie-Studio 控制面板"
    echo ""
    echo "用法:"
    echo "  ./run.sh              打开交互式控制面板（推荐）"
    echo "  ./run.sh [命令]       直接执行命令"
    echo ""
    echo "命令:"
    echo "  start [--prod]       启动服务（--prod 为生产模式）"
    echo "  stop                 停止所有服务"
    echo "  restart [--prod]     重启服务"
    echo "  status               查看服务状态"
    echo "  logs [backend|frontend]  查看日志"
    echo "  install              安装所有依赖"
    echo "  update [--auto]      更新到最新版本"
    echo "  auto-update [enable|disable|status]"
    echo "  rollback             回滚到上一个版本"
    echo "  network [on|off|status]  公网访问开关"
    echo "  port [backend|frontend] <端口号>"
    echo "                       修改服务端口"
    echo "  test                 运行后端测试"
    echo "  optimize             检测服务器并应用推荐配置"
    echo "  clean                清理缓存/重置依赖"
    echo "  version              版本信息"
    echo ""
}

# ======================
# 主程序
# ======================

main() {
    cd "$PROJECT_DIR"

    # 检查 --prod 标志
    for arg in "$@"; do
        if [ "$arg" = "--prod" ]; then
            RUN_MODE="prod"
        fi
    done

    # 无参数时进入交互式菜单
    if [ $# -eq 0 ]; then
        menu_main
        exit 0
    fi

    # 有参数时使用命令行模式（兼容脚本/cron 调用）
    case "$1" in
        start)
            start_all
            ;;
        stop)
            stop_all
            ;;
        restart)
            stop_all
            sleep 2
            start_all
            ;;
        status)
            show_status
            ;;
        install)
            install_all_deps
            ;;
        update)
            shift
            update_project "$@"
            ;;
        auto-update)
            shift
            auto_update_manage "$@"
            ;;
        rollback)
            rollback_version
            ;;
        test)
            run_tests
            ;;
        optimize)
            maybe_offer_performance_profile "manual" "true"
            ;;
        port)
            shift
            local target="${1:-}"
            local new_port="${2:-}"
            if [ -z "$target" ] || [ -z "$new_port" ]; then
                echo "当前端口:  后端 $BACKEND_PORT  /  前端 $FRONTEND_PORT"
                echo ""
                echo "用法: $0 port [backend|frontend] <端口号>"
                echo "  $0 port backend 9000"
                echo "  $0 port frontend 3001"
            elif ! [[ "$new_port" =~ ^[0-9]+$ ]] || [ "$new_port" -lt 1024 ] || [ "$new_port" -gt 65535 ]; then
                log_error "无效端口号（需 1024-65535）"
                exit 1
            elif [ "$target" = "backend" ]; then
                BACKEND_PORT="$new_port"
                save_config
                log_success "后端端口已设置为 $BACKEND_PORT"
            elif [ "$target" = "frontend" ]; then
                FRONTEND_PORT="$new_port"
                save_config
                log_success "前端端口已设置为 $FRONTEND_PORT"
            else
                log_error "未知目标: $target（可选: backend, frontend）"
                exit 1
            fi
            ;;
        clean)
            clean_project
            ;;
        network)
            shift
            case "${1:-}" in
                on)
                    LISTEN_HOST="0.0.0.0"
                    save_config
                    log_success "公网访问已开启 (http://$(get_server_ip):$BACKEND_PORT)"
                    log_warn "请重启服务使设置生效"
                    ;;
                off)
                    LISTEN_HOST="127.0.0.1"
                    save_config
                    log_success "公网访问已关闭 (仅 localhost)"
                    log_warn "请重启服务使设置生效"
                    ;;
                domain)
                    shift
                    case "${1:-}" in
                        set)
                            if [ -z "${2:-}" ]; then
                                echo "用法: $0 network domain set <域名>[,<域名2>,...]"
                                exit 1
                            fi
                            ALLOWED_DOMAINS=$(echo "$2" | tr -d ' ')
                            if [ "$LISTEN_HOST" != "0.0.0.0" ]; then
                                LISTEN_HOST="0.0.0.0"
                            fi
                            save_config
                            log_success "域名已绑定: $ALLOWED_DOMAINS"
                            log_warn "请重启服务使设置生效"
                            ;;
                        clear)
                            ALLOWED_DOMAINS=""
                            save_config
                            log_success "已清除绑定域名"
                            log_warn "请重启服务使设置生效"
                            ;;
                        *)
                            if [ -n "$ALLOWED_DOMAINS" ]; then
                                echo "绑定域名: $ALLOWED_DOMAINS"
                            else
                                echo "绑定域名: 无"
                            fi
                            echo "用法: $0 network domain [set <域名>|clear]"
                            ;;
                    esac
                    ;;
                status|"")
                    if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
                        echo "公网访问: 已开启 (http://$(get_server_ip):$BACKEND_PORT)"
                    else
                        echo "公网访问: 已关闭 (仅 localhost)"
                    fi
                    if [ -n "$ALLOWED_DOMAINS" ]; then
                        echo "绑定域名: $ALLOWED_DOMAINS"
                    else
                        echo "绑定域名: 无"
                    fi
                    ;;
                *)
                    echo "用法: $0 network [on|off|domain|status]"
                    ;;
            esac
            ;;
        version|--version|-v)
            show_version
            ;;
        logs)
            show_logs "$2"
            ;;
        attach)
            attach_session "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
