# 部署流程与脚本模式

单机 Docker 部署的完整流程，覆盖本地测试环境与生产服务器增量发布。核心目标：**零数据丢失、失败即中断、结果可验证**。

## 环境拓扑

```
本地开发 → 本地 Docker（compose，命名卷）→ 生产服务器（SSH 远程，bind mount）
                                              └─ Nginx 子路径反代 /xxx/ → 容器端口
```

- 本地：`docker compose up -d --build`，数据在命名卷，`down` 不带 `-v` 即保数据
- 生产：`scripts/deploy.sh prod`，打包源码 scp → 服务器本机构建镜像 → 换容器
- Nginx 独立编排，与应用通过外部共享 docker 网络互通

## 部署脚本设计原则

1. **凭据只走环境变量**：`DEPLOY_SSH_HOST` / `DEPLOY_SSH_PASS` / `DEPLOY_APP_PORT`…，脚本内零硬编码
2. **失败即中断**：每步检查退出码；严禁 `cmd 2>/dev/null; echo OK` 吞错谎报（本项目真实事故：docker rm 失败被吞掉，后续 create 撞名，脚本却一路报成功）
3. **只读预检先行**：部署前采集基线——现有容器 Env/挂载/镜像 ID、迁移版本、关键表行数
4. **配置沿用而非覆盖**：CORS 白名单等运行时配置从旧容器 `docker inspect` 读取沿用，避免抹掉线上已有配置（如公网入口来源）
5. **结果验证闭环**：新容器镜像 ID == 新构建镜像 ID；迁移版本 == 预期；行数逐项对比

## 生产部署标准流程

```
部署检查单：
- [ ] 1. 只读预检：容器配置/数据目录/迁移版本/行数基线
- [ ] 2. WAL 感知备份数据库（并拉回本机一份）
- [ ] 3. 打包源码上传（排除 venv/__pycache__/*.db/uploads）
- [ ] 4. 服务器本机构建新镜像（避免跨架构问题，如 ARM 服务器）
- [ ] 5. 停旧容器 → 删除 → 用新镜像 create → 启动
- [ ] 6. 健康检查轮询直至 200（上限 180s）
- [ ] 7. 验证：镜像一致性/迁移版本/行数对比/功能冒烟
- [ ] 8. 记录部署日志与备份文件位置
```

### 关键步骤代码模式

**WAL 感知备份**（在容器内执行）：

```bash
docker exec $APP python -c "import sqlite3;\
s=sqlite3.connect('/data/app.db');\
d=sqlite3.connect('/data/backups/app_$(date +%Y%m%d_%H%M%S).db');\
s.backup(d)"
```

**systemd 感知的容器切换**（先探测再选启停方式）：

```bash
# 服务器可能用 systemd 单元（ExecStart=docker start -a xxx, Restart=always）托管容器。
# 直接 docker stop 会被 5 秒内拉起旧容器，导致 rm 失败、create 撞名。
if ssh $HOST "systemctl cat ${UNIT}.service" >/dev/null 2>&1; then
    ssh $HOST "systemctl stop $UNIT"          # 经 systemd 停
else
    ssh $HOST "docker stop -t 15 $APP"
fi
# 删除必须验证成功，失败重试后仍在则中断并恢复服务
ssh $HOST "docker rm $APP" || { ssh $HOST "systemctl start $UNIT"; exit 1; }
# 用 docker create + systemctl start（而非 docker run）保持与托管方式一致
```

**健康检查轮询**（迁移可能耗时 20s+，低配 ARM 机更慢）：

```bash
for i in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://localhost:$PORT/api/health)
    [ "$code" = "200" ] && { echo "HEALTH_OK after $((i*3))s"; break; }
    sleep 3
done
```

**部署后验证**：

```bash
# 1. 容器跑的确实是新镜像
[ "$(docker inspect $APP -f '{{.Image}}')" = "$(docker inspect $IMG -f '{{.Id}}')" ]
# 2. 迁移版本到位
docker exec $APP python -c "import sqlite3;print(sqlite3.connect('/data/app.db')\
.execute('select version_num from alembic_version').fetchone())"
# 3. 关键表行数与基线逐项对比（零丢失证明）
# 4. 经 Nginx 入口冒烟：页面 200、静态资源 200、关键 API 返回正确
```

## 数据持久化规则

- 容器内数据统一挂 `/data`（`DB_PATH=/data/app.db`、`UPLOAD_DIR=/data/uploads`、备份 `/data/backups/`）
- 本地用命名卷、生产用 bind mount 均可，但**部署脚本的数据目录默认值必须与线上实际挂载一致**——动手前用 `docker inspect` 核实，挂错空目录等于"数据丢失"
- bind mount 场景：宿主目录 `chown -R <appuser-uid>` 或依赖入口脚本自愈

## 回滚预案

- 备份文件三处留存：容器内 `/data/backups/`、宿主数据目录、拉回本机
- 回滚 = 停容器 → 还原备份 db → 用旧镜像重建容器（旧镜像不要立即 `docker rmi`）
- `.secret_key` 不动则用户 token 全程有效

## 常见部署故障排查

| 症状 | 大概率原因 | 排查命令 |
|------|-----------|---------|
| create/run 报容器名冲突 | 看门狗（systemd/cron）拉起了旧容器 | `systemctl list-units \| grep -i <app>`；`grep -rIl <容器名> /etc/systemd/` |
| 启动崩溃循环 | 数据目录属主不对 / 密钥校验失败 | `docker logs`；`ls -ln <数据目录>` |
| 健康检查一直不过 | 迁移耗时长 / 迁移失败 | `docker logs` 看 alembic 输出 |
| 部署后行为没变 | 容器还在跑旧镜像 | 对比 `.Image` 与新镜像 Id |
| 外网跨域失败 | 重建时 CORS 白名单被默认值覆盖 | `docker inspect -f '{{.Config.Env}}'` |
