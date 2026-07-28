#!/usr/bin/env bash
# ============================================================================
# 暑假作业打卡系统 —— 增量部署脚本
# 用途：在不删除数据库的前提下，更新应用代码并执行数据库迁移
# ============================================================================
# 用法：
#   ./deploy.sh local      # 本地 Docker 增量更新
#   DEPLOY_SSH_HOST=<服务器IP> DEPLOY_SSH_PASS=xxx ./deploy.sh prod       # 生产服务器增量更新
#   DEPLOY_SSH_HOST=<服务器IP> DEPLOY_SSH_PASS=xxx ./deploy.sh prod --no-backup  # 跳过备份
#
# 环境变量（生产部署）：
#   DEPLOY_SSH_HOST      必填，生产服务器地址
#   DEPLOY_SSH_PASS      必填，SSH 密码（建议改用密钥登录后置空）
#   DEPLOY_SSH_USER      选填，默认 root
#   DEPLOY_SSH_PORT      选填，默认 22
#   DEPLOY_APP_PORT      选填，默认 9000
#   DEPLOY_ALLOWED_ORIGINS 选填，CORS 白名单（逗号分隔），默认根据 DEPLOY_SSH_HOST 生成
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

    SSH_USER="${DEPLOY_SSH_USER:-root}"
    SSH_HOST="${DEPLOY_SSH_HOST:?请设置环境变量 DEPLOY_SSH_HOST（生产服务器地址）}"
    SSH_PASS="${DEPLOY_SSH_PASS:?请设置环境变量 DEPLOY_SSH_PASS}"
    SSH_PORT="${DEPLOY_SSH_PORT:-22}"
    APP_PORT="${DEPLOY_APP_PORT:-9000}"
    APP_UID="10001"   # Dockerfile 中 appuser 的 uid（非 root 容器）
    DEPLOY_DIR="/tmp/summer-homework-checkin"
    # 生产服务器上现行容器 bind mount 的真实数据目录
    DATA_DIR="${DEPLOY_DATA_DIR:-/opt/homework-deploy/data}"
    # CORS 白名单：未显式指定时根据目标地址生成
    ALLOWED_ORIGINS="${DEPLOY_ALLOWED_ORIGINS:-http://$SSH_HOST:$APP_PORT,http://localhost:$APP_PORT}"

    log_info "===== 生产服务器增量更新 ====="
    log_warn "目标: $SSH_USER@$SSH_HOST:$APP_PORT"

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
    # COPYFILE_DISABLE=1 禁止 macOS tar 打包 AppleDouble（._*）元数据文件，
    # 否则 ._*.py 会被 alembic 误加载导致 "source code string cannot contain null bytes"
    COPYFILE_DISABLE=1 tar czf - -C "$PROJECT_DIR" --exclude='._*' --exclude='.DS_Store' summer-homework-checkin/ | \
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
            "cat > /tmp/homework-deploy-update.tar.gz && cd /tmp && rm -rf $DEPLOY_DIR && tar xzf homework-deploy-update.tar.gz && rm homework-deploy-update.tar.gz && echo 'TRANSFER_OK'"

    # 3. 重新构建 Docker 镜像（root 用户无需 sudo）
    log_info "重新构建 Docker 镜像..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "docker build -t summer-homework-img $DEPLOY_DIR/ 2>&1 | tail -3"

    # 4. 停止旧容器（保留数据卷）
    log_info "停止旧容器..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "docker stop summer-homework 2>/dev/null; echo 'STOPPED'"

    # 5. 删除旧容器（不删除 volume）
    log_info "删除旧容器（保留数据卷）..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "docker rm summer-homework 2>/dev/null; echo 'REMOVED'"

    # 6. 启动新容器（挂载原有数据卷）
    log_info "启动新容器（挂载原有数据）..."
    # 检查密钥文件是否存在
    if ! sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "test -f $DATA_DIR/.secret_key"; then
        log_error "生产服务器缺少密钥文件: $DATA_DIR/.secret_key"
        log_error "请先在服务器上生成密钥: openssl rand -hex 32 > $DATA_DIR/.secret_key"
        exit 1
    fi
    # 关键：容器以非 root 用户 appuser(uid $APP_UID) 运行，bind mount 的宿主数据目录
    # 需将属主调整为 appuser，否则容器无法写入 app.db / uploads（仅改属主，不动数据）
    log_info "调整数据目录属主为 appuser(uid $APP_UID) 以适配非 root 容器..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "chown -R $APP_UID:$APP_UID $DATA_DIR && echo 'CHOWN_OK'"
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "docker run -d --name summer-homework --restart unless-stopped \
            -p $APP_PORT:8000 \
            -e DB_PATH=/data/app.db \
            -e UPLOAD_DIR=/data/uploads \
            -e SUMMER_SECRET=\$(cat $DATA_DIR/.secret_key) \
            -e ALLOWED_ORIGINS=$ALLOWED_ORIGINS \
            -v $DATA_DIR:/data \
            summer-homework-img 2>&1"

    # 7. 验证
    log_info "等待服务启动..."
    sleep 10

    local HEALTH
    HEALTH=$(sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "curl -sf http://localhost:$APP_PORT/api/health 2>/dev/null || echo 'FAIL'")

    if [[ "$HEALTH" == *"ok"* ]]; then
        log_info "生产服务验证通过: http://$SSH_HOST:$APP_PORT/api/health"
    else
        log_error "生产服务验证失败！"
        log_error "数据库备份位置: $DATA_DIR/backups/"
        log_error "排查命令: sshpass -p '****' ssh -p $SSH_PORT $SSH_USER@$SSH_HOST \"docker logs summer-homework\""
        exit 1
    fi

    # 8. 显示迁移日志
    log_info "迁移日志:"
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
        "docker logs summer-homework 2>&1 | head -15"

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
        echo "  prod    生产服务器增量更新（需设置 DEPLOY_SSH_HOST / DEPLOY_SSH_PASS）"
        echo "  --no-backup  跳过数据库备份（不推荐用于生产）"
        exit 1
        ;;
esac
