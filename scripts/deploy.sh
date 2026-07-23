#!/usr/bin/env bash
# ============================================================================
# 暑假作业打卡系统 —— 增量部署脚本
# 用途：在不删除数据库的前提下，更新应用代码并执行数据库迁移
# ============================================================================
# 用法：
#   ./deploy.sh local      # 本地 Docker 增量更新
#   DEPLOY_SSH_PASS=xxx ./deploy.sh prod       # 生产服务器增量更新
#   DEPLOY_SSH_PASS=xxx ./deploy.sh prod --no-backup  # 跳过备份
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SUMMER_DIR="$PROJECT_DIR/summer-homework-checkin"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---- 本地部署 ----
deploy_local() {
    log_info "===== 本地 Docker 增量更新 ====="

    cd "$PROJECT_DIR"

    # 1. 备份本地数据库（从 volume 中复制）
    log_info "备份本地数据库..."
    LOCAL_BACKUP_DIR="$PROJECT_DIR/.backups/local"
    mkdir -p "$LOCAL_BACKUP_DIR"
    if docker cp summer-homework:/data/app.db "$LOCAL_BACKUP_DIR/app_$(date +%Y%m%d_%H%M%S).db" 2>/dev/null; then
        log_info "本地数据库已备份到 $LOCAL_BACKUP_DIR/"
    else
        log_warn "本地数据库不存在或容器未运行，跳过备份"
    fi

    # 2. 重新构建并启动（保留 volume 数据）
    log_info "重新构建镜像并启动容器（保留数据卷）..."
    docker compose up -d --build summer-homework

    # 3. 验证
    sleep 5
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        log_info "本地服务验证通过: http://localhost:8000/api/health"
    else
        log_error "本地服务验证失败，请检查日志: docker logs summer-homework"
        exit 1
    fi

    log_info "===== 本地增量更新完成 ====="
    log_info "查看迁移日志: docker logs summer-homework | head -20"
}

# ---- 生产部署 ----
deploy_prod() {
    local SKIP_BACKUP=false
    if [[ "${2:-}" == "--no-backup" ]]; then
        SKIP_BACKUP=true
    fi

    SSH_USER="qihang"
    SSH_HOST="192.168.1.112"
    SSH_PASS="${DEPLOY_SSH_PASS:?请设置环境变量 DEPLOY_SSH_PASS}"
    SSH_PORT="22"
    DEPLOY_DIR="/tmp/summer-homework-checkin"
    DATA_DIR="/var/services/homes/qihang/homework-deploy/data"

    log_info "===== 生产服务器增量更新 ====="
    log_warn "目标: $SSH_USER@$SSH_HOST"

    if [[ "$SKIP_BACKUP" == "false" ]]; then
        # 1. 备份生产数据库
        log_info "备份生产数据库..."
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
            "mkdir -p $DATA_DIR/backups && cp $DATA_DIR/app.db $DATA_DIR/backups/app_\$(date +%Y%m%d_%H%M%S).db && echo 'BACKUP_OK'"
        log_info "生产数据库已备份到 $DATA_DIR/backups/"
    else
        log_warn "跳过数据库备份（使用了 --no-backup）"
    fi

    # 2. 传输更新后的代码
    log_info "传输更新代码到服务器..."
    tar czf - -C "$PROJECT_DIR" summer-homework-checkin/ | \
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
            "cat > /tmp/homework-deploy-update.tar.gz && cd /tmp && rm -rf $DEPLOY_DIR && tar xzf homework-deploy-update.tar.gz && rm homework-deploy-update.tar.gz && echo 'TRANSFER_OK'"

    # 3. 重新构建 Docker 镜像
    log_info "重新构建 Docker 镜像..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "echo '$SSH_PASS' | sudo -S docker build -t summer-homework-img $DEPLOY_DIR/ 2>&1 | tail -3"

    # 4. 停止旧容器（保留数据卷）
    log_info "停止旧容器..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "echo '$SSH_PASS' | sudo -S docker stop summer-homework 2>/dev/null; echo 'STOPPED'"

    # 5. 删除旧容器（不删除 volume）
    log_info "删除旧容器（保留数据卷）..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "echo '$SSH_PASS' | sudo -S docker rm summer-homework 2>/dev/null; echo 'REMOVED'"

    # 6. 启动新容器（挂载原有数据卷）
    log_info "启动新容器（挂载原有数据）..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "echo '$SSH_PASS' | sudo -S docker run -d --name summer-homework --restart unless-stopped \
            -p 6565:8000 \
            -e DB_PATH=/data/app.db \
            -e UPLOAD_DIR=/data/uploads \
            -e SUMMER_SECRET=\$(cat $DATA_DIR/.secret_key 2>/dev/null || echo 'fallback-secret') \
            -e ALLOWED_ORIGINS=http://192.168.1.112:6565,http://localhost:6565 \
            -v $DATA_DIR:/data \
            summer-homework-img 2>&1"

    # 7. 验证
    log_info "等待服务启动..."
    sleep 10

    local HEALTH
    HEALTH=$(sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "curl -sf http://localhost:6565/api/health 2>/dev/null || echo 'FAIL'")

    if [[ "$HEALTH" == *"ok"* ]]; then
        log_info "生产服务验证通过: http://192.168.1.112:6565/api/health"
    else
        log_error "生产服务验证失败！"
        log_error "数据库备份位置: $DATA_DIR/backups/"
        log_error "回滚命令: sshpass -p '$SSH_PASS' ssh -p $SSH_PORT $SSH_USER@$SSH_HOST \"echo '$SSH_PASS' | sudo -S docker logs summer-homework\""
        exit 1
    fi

    # 8. 显示迁移日志
    log_info "迁移日志:"
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "echo '$SSH_PASS' | sudo -S docker logs summer-homework 2>&1 | head -15"

    log_info "===== 生产增量更新完成 ====="
}

# ---- 主入口 ----
case "${1:-}" in
    local)
        deploy_local
        ;;
    prod)
        deploy_prod "$@"
        ;;
    *)
        echo "用法: $0 {local|prod} [--no-backup]"
        echo ""
        echo "  local   本地 Docker 增量更新（保留数据卷）"
        echo "  prod    生产服务器 (192.168.1.112) 增量更新"
        echo "  --no-backup  跳过数据库备份（不推荐用于生产）"
        exit 1
        ;;
esac
