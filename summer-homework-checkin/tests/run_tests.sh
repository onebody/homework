#!/usr/bin/env bash
# ============================================================================
# 暑假作业打卡系统 —— 回归测试运行脚本
# ============================================================================
# 用法：
#   bash tests/run_tests.sh                           # 全量回归测试
#   bash tests/run_tests.sh -k "login"                # 筛选测试
#   bash tests/run_tests.sh test_auth.py              # 指定模块
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       暑假作业打卡系统 - 回归测试                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 1. 检查依赖
log_info "检查依赖..."
python3 -c "import pytest, requests" 2>/dev/null || {
    log_info "安装测试依赖..."
    pip install pytest requests pillow -q
}

# 2. 检查后端服务
API_BASE="${API_BASE_URL:-http://localhost:8000}"
log_info "检查后端服务 $API_BASE ..."

if ! curl -sf "$API_BASE/api/health" > /dev/null 2>&1; then
    log_warn "后端服务未运行，尝试启动..."

    # 检查是否已有 Docker 容器
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "summer-homework"; then
        log_info "Docker 容器 summer-homework 正在运行，使用 http://localhost:8000"
    else
        log_error "后端服务不可用！"
        log_error "请先启动服务："
        log_error "  Docker:  cd $PROJECT_DIR && docker compose up -d summer-homework"
        log_error "  本地:    cd $BACKEND_DIR && python migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"
        exit 1
    fi
fi

log_info "✅ 后端服务正常运行"

# 3. 运行测试
log_info "运行回归测试..."

cd "$SCRIPT_DIR"

PYTHONDONTWRITEBYTECODE=1 RATE_LIMIT_ENABLED=0 python -m pytest "$SCRIPT_DIR" -v "$@"
EXIT_CODE=$?

# 4. 输出结果
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    log_info "✅ 全部回归测试通过！"
else
    log_error "❌ 部分测试失败（退出码: $EXIT_CODE）"
    log_error "请检查上方日志定位失败原因。"
fi

exit $EXIT_CODE
