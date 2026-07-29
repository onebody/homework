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
#   DEPLOY_ALLOWED_ORIGINS 选填，CORS 白名单（逗号分隔）；默认沿用服务器现有容器的配置，
#                        避免把线上已存在的来源（如公网入口）覆盖掉
#   DEPLOY_DATA_DIR      选填，服务器数据目录，默认 /opt/homework-deploy/data
#   DEPLOY_SYSTEMD_UNIT  选填，托管容器的 systemd 单元名，默认 homework
#   DEPLOY_HEALTH_TIMEOUT 选填，健康检查最长等待秒数，默认 180
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

    # 3. 验证（轮询而非固定等待：容器启动时要先跑数据库迁移）
    log_info "等待本地服务就绪..."
    LOCAL_OK=false
    for _ in $(seq 1 40); do
        if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then LOCAL_OK=true; break; fi
        sleep 3
    done
    if [[ "$LOCAL_OK" == "true" ]]; then
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
    # 托管容器的 systemd 单元名（形如 ExecStart=/usr/bin/docker start -a <container>）
    SYSTEMD_UNIT="${DEPLOY_SYSTEMD_UNIT:-homework}"
    # 健康检查总时长：容器启动要先跑 alembic 迁移，低配/ARM 机器常需 20s 以上
    HEALTH_TIMEOUT="${DEPLOY_HEALTH_TIMEOUT:-180}"
    TS="$(date +%Y%m%d_%H%M%S)"

    rexec() { sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" "$@"; }

    log_info "===== 生产服务器增量更新 ====="
    log_warn "目标: $SSH_USER@$SSH_HOST:$APP_PORT"

    # 探测容器托管方式。若存在 systemd 单元，它会在 docker stop 后于 RestartSec 内
    # 用 `docker start -a` 把【旧容器】重新拉起，导致 docker rm 失败、docker run 撞名冲突。
    # 因此必须改用 systemctl 启停，而不是直接操作 docker。
    USE_SYSTEMD=false
    if rexec "systemctl cat ${SYSTEMD_UNIT}.service" >/dev/null 2>&1; then
        USE_SYSTEMD=true
        log_warn "检测到 systemd 单元 ${SYSTEMD_UNIT}.service，将通过 systemctl 启停"
    else
        log_info "未检测到 systemd 单元，直接用 docker 管理容器"
    fi

    # CORS 白名单：未显式指定时沿用服务器现有容器的值，避免抹掉线上已有来源（如公网入口）
    ALLOWED_ORIGINS="${DEPLOY_ALLOWED_ORIGINS:-}"
    if [[ -z "$ALLOWED_ORIGINS" ]]; then
        ALLOWED_ORIGINS="$(rexec "docker inspect summer-homework --format '{{range .Config.Env}}{{println .}}{{end}}'" 2>/dev/null | sed -n 's/^ALLOWED_ORIGINS=//p' | tr -d '\r' || true)"
    fi
    if [[ -z "$ALLOWED_ORIGINS" ]]; then
        ALLOWED_ORIGINS="http://$SSH_HOST:$APP_PORT,http://localhost:$APP_PORT"
        log_warn "未能读取现有 CORS 白名单，使用默认值: $ALLOWED_ORIGINS"
    else
        log_info "沿用现有 CORS 白名单: $ALLOWED_ORIGINS"
    fi

    if [[ "$SKIP_BACKUP" == "false" ]]; then
        # 1. 备份生产数据库
        # 注意：SQLite 处于 WAL 模式时，裸 cp app.db 会丢掉尚未 checkpoint 的 -wal 数据，
        # 因此优先用 sqlite3 backup API 生成一致性快照。
        log_info "备份生产数据库（WAL 一致性快照）..."
        if rexec "docker exec summer-homework python -c \"import sqlite3;s=sqlite3.connect('/data/app.db');d=sqlite3.connect('/data/backups/app_$TS.db');s.backup(d);d.close();s.close()\"" 2>/dev/null; then
            log_info "已备份到 $DATA_DIR/backups/app_$TS.db（含 WAL 内容）"
        else
            log_warn "容器内快照失败，回退为文件级拷贝（同时保留 -wal/-shm）"
            rexec "mkdir -p $DATA_DIR/backups/raw_$TS && cd $DATA_DIR && cp app.db app.db-wal app.db-shm backups/raw_$TS/ 2>/dev/null; cp app.db backups/app_$TS.db && echo 'BACKUP_OK'"
            log_info "已备份到 $DATA_DIR/backups/raw_$TS/"
        fi
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

    # 4. 停止旧服务（systemd 托管时必须用 systemctl，否则容器会在几秒内被自动拉起）
    log_info "停止旧服务..."
    if [[ "$USE_SYSTEMD" == "true" ]]; then
        rexec "systemctl stop ${SYSTEMD_UNIT}; sleep 3; echo 'STOPPED'" || true
    else
        rexec "docker stop -t 15 summer-homework >/dev/null 2>&1; echo 'STOPPED'" || true
    fi

    # 5. 删除旧容器（保留数据目录）
    # 关键：删除失败必须中断部署并暴露原因。旧版本用 `docker rm ... 2>/dev/null; echo REMOVED`
    # 会把失败吞掉并谎报成功，导致后续 docker run 撞名退出 125、部署静默失效。
    log_info "删除旧容器（保留数据）..."
    if rexec "bash -s" <<'EOS'
for i in 1 2 3; do
    docker rm summer-homework >/dev/null 2>&1 && exit 0
    docker stop -t 15 summer-homework >/dev/null 2>&1
    sleep 3
done
docker ps -a --format '{{.Names}}' | grep -qx summer-homework && exit 1
exit 0
EOS
    then
        log_info "旧容器已删除"
    else
        log_error "旧容器无法删除，可能被 systemd 或看门狗持续拉起"
        log_error "请登录服务器排查: systemctl stop ${SYSTEMD_UNIT}; docker rm -f summer-homework"
        if [[ "$USE_SYSTEMD" == "true" ]]; then
            log_warn "正尝试恢复原服务..."
            rexec "systemctl start ${SYSTEMD_UNIT}" || true
        fi
        exit 1
    fi

    # 6. 校验密钥文件（缺失会导致所有已登录 token 失效）
    if ! rexec "test -f $DATA_DIR/.secret_key"; then
        log_error "生产服务器缺少密钥文件: $DATA_DIR/.secret_key"
        log_error "请先在服务器上生成密钥: openssl rand -hex 32 > $DATA_DIR/.secret_key"
        exit 1
    fi

    # 关键：容器以非 root 用户 appuser(uid $APP_UID) 运行，bind mount 的宿主数据目录
    # 需将属主调整为 appuser，否则容器无法写入 app.db / uploads（仅改属主，不动数据）
    log_info "调整数据目录属主为 appuser(uid $APP_UID) 以适配非 root 容器..."
    rexec "chown -R $APP_UID:$APP_UID $DATA_DIR && echo 'CHOWN_OK'"

    # 7. 用新镜像创建容器（挂载原有数据目录），再交由 systemd/docker 启动
    log_info "以新镜像创建容器..."
    rexec "docker create --name summer-homework --restart unless-stopped \
            -p $APP_PORT:8000 \
            -e DB_PATH=/data/app.db \
            -e UPLOAD_DIR=/data/uploads \
            -e SUMMER_SECRET=\$(cat $DATA_DIR/.secret_key) \
            -e ALLOWED_ORIGINS='$ALLOWED_ORIGINS' \
            -v $DATA_DIR:/data \
            summer-homework-img >/dev/null && echo 'CREATED'"

    log_info "启动服务..."
    if [[ "$USE_SYSTEMD" == "true" ]]; then
        rexec "systemctl start ${SYSTEMD_UNIT} && echo 'STARTED'"
    else
        rexec "docker start summer-homework >/dev/null && echo 'STARTED'"
    fi

    # 8. 验证：轮询健康检查
    # 旧版本固定 sleep 10 就判定，而容器启动需先跑迁移（ARM/低配机器实测 20s+），会误报失败。
    log_info "等待服务就绪（最多 ${HEALTH_TIMEOUT}s）..."
    if rexec "APP_PORT=$APP_PORT HEALTH_TIMEOUT=$HEALTH_TIMEOUT bash -s" <<'EOS'
attempts=$((HEALTH_TIMEOUT / 3))
for i in $(seq 1 "$attempts"); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://localhost:$APP_PORT/api/health" 2>/dev/null)
    if [ "$code" = "200" ]; then
        echo "HEALTH_OK after $((i * 3))s"
        exit 0
    fi
    sleep 3
done
exit 1
EOS
    then
        log_info "生产服务验证通过: http://$SSH_HOST:$APP_PORT/api/health"
    else
        log_error "生产服务验证失败！"
        log_error "数据库备份位置: $DATA_DIR/backups/"
        log_error "排查命令: ssh $SSH_USER@$SSH_HOST \"docker logs summer-homework\""
        exit 1
    fi

    # 9. 显示迁移日志，并校验容器确实跑在新镜像上
    log_info "迁移日志:"
    rexec "docker logs summer-homework 2>&1 | head -15" || true
    log_info "镜像一致性校验（两行应相同）:"
    rexec "echo -n '  running: '; docker inspect summer-homework --format '{{.Image}}'; echo -n '  built:   '; docker inspect summer-homework-img --format '{{.Id}}'" || true

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
