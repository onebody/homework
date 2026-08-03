# 生产部署交接清单（暑假作业打卡系统）

- 适用版本：安全整改 v1.2（含 V-02 上传认证化、分页功能、pager 标签修复）
- 执行方式：**由负责人在生产服务器与本机自行执行**，本文档逐条可粘贴
- 关联文档：[SECURITY_REMEDIATION_REPORT.md](./SECURITY_REMEDIATION_REPORT.md)

---

## 第 0 步：部署前提条件核对

1. 本仓库代码为待发布状态（工作区干净、已提交）
2. 本地 `scripts/deploy.sh` 语法通过：`bash -n scripts/deploy.sh`
3. 服务器可达且磁盘有余量（`df -h /opt`）
4. **数据库与上传文件不受部署影响**：生产数据位于服务器 bind mount 目录
   （默认 `/opt/homework-deploy/data`），部署脚本不删除、不清空该目录；
   seed 为幂等设计，已有数据时自动跳过

## 第 1 步：部署前只读探测（在生产服务器上执行，共 3 条）

```bash
# 探测 1（V-05 前置，决定第 2 步的 DEPLOY_BIND_ADDR）：确认 Nginx upstream 指向
grep -r 'proxy_pass' /etc/nginx/ 2>/dev/null; docker ps --format '{{.Names}} {{.Ports}}'
```

判读规则：
- upstream 是 `127.0.0.1:<端口>` 或 `localhost:<端口>` → 保持默认 `DEPLOY_BIND_ADDR=127.0.0.1`
- upstream 是宿主局域网 IP（如 `192.168.x.x:<端口>`）→ 必须显式 `DEPLOY_BIND_ADDR=0.0.0.0`，否则部署后 502

```bash
# 探测 2（V-04）：确认生产容器环境变量是否残留弱口令初始化密码
docker inspect summer-homework --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -i ADMIN
```

判读规则：输出应为空，或 `ADMIN_INIT_PASSWORD=` 后为空。若残留 `admin123`，
记录待清理（新容器创建时本脚本不再注入该变量，但需确认生产库 admin 口令非弱口令）。

```bash
# 探测 3（V-11）：确认生产密钥文件权限
stat -c '%a %U %n' /opt/homework-deploy/data/.secret_key
```

判读规则：期望 `600`；若是 `644`，执行 `chmod 600 /opt/homework-deploy/data/.secret_key`。
**该文件不可删除或更换内容**——它是 JWT 签名密钥，更换会导致所有已登录用户 token 失效。

## 第 2 步：执行部署（在本机仓库根目录执行）

```bash
# 推荐：密钥认证
DEPLOY_SSH_HOST=<服务器IP> \
DEPLOY_SSH_KEY=~/.ssh/id_ed25519 \
./scripts/deploy.sh prod
```

可选覆盖项（默认值与脚本一致，按需追加）：

| 变量 | 默认 | 何时需要修改 |
|------|------|--------------|
| `DEPLOY_SSH_USER` | `root` | 生产 SSH 用户非 root |
| `DEPLOY_SSH_PORT` | `22` | SSH 端口非 22 |
| `DEPLOY_APP_PORT` | `9000` | Nginx upstream 端口不是 9000（须与探测 1 一致） |
| `DEPLOY_BIND_ADDR` | `127.0.0.1` | 探测 1 判定 upstream 非本机回连时设为 `0.0.0.0` |
| `DEPLOY_DATA_DIR` | `/opt/homework-deploy/data` | 生产数据目录不同 |
| `DEPLOY_SYSTEMD_UNIT` | `homework` | systemd 单元名不同 |
| `DEPLOY_ALLOWED_ORIGINS` | 沿用旧容器（自动剔除 localhost） | 沿用结果为空时脚本会中断，此时显式指定，如 `http://<生产域名>` |
| `DEPLOY_READONLY_FS` | `0` | 生产 bind mount 与本地命名卷不同构，**本轮保持 0，勿开** |
| `DEPLOY_HEALTH_TIMEOUT` | `180` | 低配机器迁移慢可加大 |

脚本自动完成的事（无需人工干预）：
- systemd 单元探测并停容器（防止被 systemd 自动拉起造成端口冲突）
- SQLite **WAL 一致性快照备份**到容器内 `/data/backups/app_<时间戳>.db`
- 代码打包（`COPYFILE_DISABLE=1` 防 macOS AppleDouble 文件）传输、服务器端构建镜像
- 容器创建自带加固项：`--security-opt no-new-privileges`、`--cap-drop ALL` + 5 项
  `--cap-add`（CHOWN/FOWNER/DAC_OVERRIDE/SETUID/SETGID，入口脚本 setpriv 降权必需）、
  内存 1G / CPU 2 限额、`-e PRODUCTION=1`（关闭 API 文档）
- 镜像一致性校验 + 健康检查轮询（默认最长 180 秒）
- 属主修正 `chown -R 10001:10001` 适配非 root 容器

## 第 3 步：部署后回归（服务器 + 浏览器）

### 3.1 服务器侧

```bash
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'   # summer-homework 应为 Up + 端口绑定符合探测 1 判定
curl -sf http://127.0.0.1:9000/api/health && echo OK      # 健康检查
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9000/docs          # 期望 404
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9000/openapi.json  # 期望 404
docker logs summer-homework 2>&1 | head -30               # 迁移日志：已有表应输出"跳过"，无报错
```

### 3.2 浏览器侧（经 Nginx 入口）

- 学生端 / 管理端均可正常登录（admin 口令为生产侧现行强口令）
- **照片回归（V-02 认证化的关键回归点）**：
  - 管理端 打卡记录 → 缩略图与灯箱大图正常显示（网络面板应为 `/api/uploads/...` 且 200）
  - 管理端 闯关任务详情 → 附件缩略图正常
  - 学生端 打卡历史照片、人脸底图正常
- **分页回归**：管理端奖品/用户/打卡/兑换/闯关/推送日志列表底部出现"第 X/Y 页 · 共 N 条"，
  翻页正常；学生端我的打卡/兑换/抽奖记录翻页正常（记录数超过每页条数时才显示控件，属预期）
- 奖品管理："新增奖品"/"编辑"弹窗可正常打开保存（本轮 pager 标签修复点）
- 群推送测试（可选）：触发一次打卡推送，确认消息送达；**不再附带照片链接属预期行为**

### 3.3 如启用 HTTPS（当前未启用，配置模板已备妥）

核对 `nginx/https.conf.example` 对应项：443 监听、证书未过期
（`openssl x509 -in <证书> -noout -enddate`）、HSTS 头、80→443 跳转。

## 第 4 步：回滚（仅当回归失败时）

部署脚本在替换容器前已自动完成 WAL 一致性数据库快照，回滚分两档：

```bash
# 档 1：仅回滚代码（数据不动）。旧镜像 tag 以部署前 docker images 为准；
# 若旧容器已被删除，用旧镜像重建后交由 systemd 托管
docker tag <旧镜像ID> summer-homework-img && systemctl restart homework

# 档 2：数据也需回退（极端情况）。快照位于容器内：
docker exec summer-homework ls /data/backups/
docker exec summer-homework cp /data/backups/app_<时间戳>.db /data/app.db
systemctl restart homework
```

回滚后重跑 3.1 与 3.2 确认恢复，并把失败现象反馈给开发侧定位。

---

## 本轮不随部署生效的事项（已决策暂缓，仅记录）

- HTTPS 全站启用：模板就绪（`nginx/https.conf.example` + `nginx/README-HTTPS.md`），待域名确定
- 后台推送配置凭证回显掩码、钉钉/企微机器人发送者白名单与 msgId 去重：暂缓，见安全报告"待处理风险"
- `/points/` 公网入口：本地 nginx 已撤销（返回 403）；生产若不托管 points-system 则无需处理
