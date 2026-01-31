#!/bin/bash
#
# MieMie-Studio 启动管理脚本
# 用法: ./run.sh [命令]
#
# 命令:
#   start     - 启动前后端服务
#   stop      - 停止所有服务
#   restart   - 重启所有服务
#   status    - 查看服务状态
#   logs      - 查看日志
#   install   - 安装依赖
#   help      - 显示帮助
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
# 环境检查
# ======================

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

check_node() {
    if ! command -v node &> /dev/null; then
        log_error "Node.js 未安装，请先安装 Node.js 18+"
        exit 1
    fi
}

check_npm() {
    if ! command -v npm &> /dev/null; then
        log_error "npm 未安装"
        exit 1
    fi
}

check_screen() {
    if ! command -v screen &> /dev/null; then
        log_error "screen 未安装，请先安装: brew install screen"
        exit 1
    fi
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
    
    log_info "创建虚拟环境..."
    PYTHON=$(check_python)
    $PYTHON -m venv "$VENV_DIR"
    log_success "虚拟环境创建完成"
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

backend_deps_installed() {
    if ! venv_exists; then
        return 1
    fi
    # 检查关键包是否安装
    "$VENV_DIR/bin/pip" show fastapi &> /dev/null
}

frontend_deps_installed() {
    [ -d "$FRONTEND_DIR/node_modules" ] && [ -f "$FRONTEND_DIR/node_modules/.package-lock.json" ]
}

install_backend_deps() {
    log_info "检查后端依赖..."
    
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
    install_backend_deps
    install_frontend_deps
    log_success "所有依赖安装完成"
}

# ======================
# 服务状态检查
# ======================

is_backend_running() {
    screen -list 2>/dev/null | grep -q "$BACKEND_SESSION"
}

is_frontend_running() {
    screen -list 2>/dev/null | grep -q "$FRONTEND_SESSION"
}

# ======================
# 服务启动
# ======================

start_backend() {
    if is_backend_running; then
        log_warn "后端服务已在运行"
        return 0
    fi
    
    # 确保依赖已安装
    if ! backend_deps_installed; then
        install_backend_deps
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    log_info "启动后端服务..."
    screen -dmS "$BACKEND_SESSION" bash -c "
        cd '$BACKEND_DIR'
        source '$VENV_DIR/bin/activate'
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 2>&1 | tee -a '$BACKEND_LOG'
    "
    
    sleep 2
    if is_backend_running; then
        log_success "后端服务已启动 (http://localhost:8000)"
    else
        log_error "后端服务启动失败，请查看日志: $BACKEND_LOG"
        return 1
    fi
}

start_frontend() {
    if is_frontend_running; then
        log_warn "前端服务已在运行"
        return 0
    fi
    
    # 确保依赖已安装
    if ! frontend_deps_installed; then
        install_frontend_deps
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    log_info "启动前端服务..."
    screen -dmS "$FRONTEND_SESSION" bash -c "
        cd '$FRONTEND_DIR'
        npm run dev -- --host 2>&1 | tee -a '$FRONTEND_LOG'
    "
    
    sleep 3
    if is_frontend_running; then
        log_success "前端服务已启动 (http://localhost:3000)"
    else
        log_error "前端服务启动失败，请查看日志: $FRONTEND_LOG"
        return 1
    fi
}

start_all() {
    check_screen
    log_info "启动 MieMie-Studio..."
    echo ""
    start_backend
    start_frontend
    echo ""
    log_success "MieMie-Studio 启动完成!"
    echo ""
    echo "  后端: http://localhost:8000"
    echo "  前端: http://localhost:3000"
    echo "  API文档: http://localhost:8000/docs"
    echo ""
    echo "使用 './run.sh logs' 查看日志"
    echo "使用 './run.sh stop' 停止服务"
}

# ======================
# 服务停止
# ======================

stop_backend() {
    if is_backend_running; then
        log_info "停止后端服务..."
        screen -S "$BACKEND_SESSION" -X quit 2>/dev/null || true
        sleep 1
        log_success "后端服务已停止"
    else
        log_info "后端服务未运行"
    fi
}

stop_frontend() {
    if is_frontend_running; then
        log_info "停止前端服务..."
        screen -S "$FRONTEND_SESSION" -X quit 2>/dev/null || true
        sleep 1
        log_success "前端服务已停止"
    else
        log_info "前端服务未运行"
    fi
}

stop_all() {
    log_info "停止 MieMie-Studio..."
    stop_backend
    stop_frontend
    log_success "MieMie-Studio 已停止"
}

# ======================
# 服务状态
# ======================

show_status() {
    echo ""
    echo "========== MieMie-Studio 状态 =========="
    echo ""
    
    # 后端状态
    if is_backend_running; then
        echo -e "  后端: ${GREEN}运行中${NC} (screen: $BACKEND_SESSION)"
    else
        echo -e "  后端: ${RED}未运行${NC}"
    fi
    
    # 前端状态
    if is_frontend_running; then
        echo -e "  前端: ${GREEN}运行中${NC} (screen: $FRONTEND_SESSION)"
    else
        echo -e "  前端: ${RED}未运行${NC}"
    fi
    
    echo ""
    
    # 环境状态
    echo "---------- 环境检查 ----------"
    
    if venv_exists; then
        echo -e "  虚拟环境: ${GREEN}已创建${NC}"
    else
        echo -e "  虚拟环境: ${YELLOW}未创建${NC}"
    fi
    
    if backend_deps_installed; then
        echo -e "  后端依赖: ${GREEN}已安装${NC}"
    else
        echo -e "  后端依赖: ${YELLOW}未安装${NC}"
    fi
    
    if frontend_deps_installed; then
        echo -e "  前端依赖: ${GREEN}已安装${NC}"
    else
        echo -e "  前端依赖: ${YELLOW}未安装${NC}"
    fi
    
    echo ""
    echo "========================================"
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
# 帮助信息
# ======================

show_help() {
    echo ""
    echo "MieMie-Studio 管理脚本"
    echo ""
    echo "用法: ./run.sh [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  start              启动前后端服务"
    echo "  stop               停止所有服务"
    echo "  restart            重启所有服务"
    echo "  status             查看服务状态"
    echo "  install            安装所有依赖"
    echo "  logs [service]     查看日志 (backend/frontend/all)"
    echo "  attach [service]   连接到 screen 会话 (backend/frontend)"
    echo "  help               显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  ./run.sh start     # 启动服务"
    echo "  ./run.sh status    # 查看状态"
    echo "  ./run.sh logs backend  # 查看后端日志"
    echo "  ./run.sh attach backend  # 连接到后端终端"
    echo ""
}

# ======================
# 主程序
# ======================

main() {
    cd "$PROJECT_DIR"
    
    case "${1:-help}" in
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
