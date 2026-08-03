# 安全渗透测试整改报告（第一、二阶段）

- 整改依据：[SECURITY_PENETRATION_TEST_REPORT.md](./SECURITY_PENETRATION_TEST_REPORT.md)
- 整改范围：第一阶段（V-02 / V-04 / V-06 / V-01）+ 第二阶段（V-03 / V-10 / V-05 / V-07 / V-08 / V-11），共 10 项
- 完成日期：2026-07-31（发布收尾核验：2026-08-03）
- 生产状态：**已于 2026-08-03 部署生产并完成全量回归**（见文末"生产部署记录"）。

---

## 整改总览

| 编号 | 漏洞 | 状态 | 修复位置 |
|------|------|------|----------|
| V-02 | 上传目录公开可遍历（人脸照片泄露） | ✅ 已修复并验证 | `backend/app/routers/uploads.py`（新增）、`main.py`、`storage.py`、`admin.py`、前端 4 个文件 |
| V-04 | admin 弱口令 admin123 | ✅ 本地已清理；⏳ 生产待探测 | `.env`、`.env.example`、本地数据库 |
| V-06 | 生产环境暴露 API 文档 | ✅ 已修复并验证 | `main.py`、`scripts/deploy.sh` |
| V-01 | 全站明文 HTTP | ✅ 配置已备妥（按决策不启用） | `nginx/https.conf.example`、`nginx/README-HTTPS.md` |
| V-03 | 部署脚本 SSH 密码明文进 argv | ✅ 已修复并验证 | `scripts/deploy.sh` |
| V-10 | SSH 主机密钥验证关闭（MITM 风险） | ✅ 已修复 | `scripts/deploy.sh` |
| V-05 | 容器端口绑定 0.0.0.0 | ✅ 本地已修复并验证；⏳ 生产待探测 | `docker-compose.yml`、`scripts/deploy.sh` |
| V-07 | 生产 CORS 含 localhost | ✅ 已修复（语法校验通过） | `scripts/deploy.sh` |
| V-08 | 容器无安全加固 | ✅ 已修复并验证 | `docker-compose.yml`、`scripts/deploy.sh` |
| V-11 | .secret_key 权限 644 | ✅ 已修复并验证 | `backend/app/config.py`、`.dockerignore`、宿主文件 |

---

## 各项修复明细与验证证据

### V-02 上传目录改为严格认证 API

**修复内容**

1. 新增 [`backend/app/routers/uploads.py`](../backend/app/routers/uploads.py)：`GET /api/uploads/{path:path}`，要求 Bearer token，且做三层校验：
   - 路径合法性（复用 `validate_upload_path`，拦截 `..`、绝对路径、realpath 逃逸）
   - **归属校验**（超出报告范围的加固，堵住本漏洞根因——用户 ID 枚举）：admin 可读全部；student 仅可读路径首段等于自己 ID 的文件；parent 仅可读已绑定孩子的文件
   - 文件存在性（404）
2. `main.py` 移除 `app.mount("/uploads", ...)` 公开挂载
3. `storage.py public_url()` 统一输出 `/api/uploads/` 前缀；`admin.py` 第 188 行的硬编码 `/uploads/` 拼装改走 `public_url()`
4. 前端 `student/app.js`、`admin/app.js` 新增 `v-auth-src` 指令（fetch + Bearer + blob + objectURL，含竞态丢弃与 objectURL 释放），`admin/index.html` 5 处、`student/index.html` 1 处绑定改造；本地 `data:` 预览图绑定保持不变

**验证证据（本地容器重建后 curl 矩阵，13/13 通过）**

| 请求 | 期望 | 实测 |
|------|------|------|
| `GET /uploads/2/<file>`（旧公开挂载） | 404 | ✅ 404 |
| `GET /api/uploads/2/<file>` 无 token | 401 | ✅ 401 |
| 学生2 取自己的文件 | 200 | ✅ 200 |
| 学生2 取学生3 的文件（越权） | 403 | ✅ 403 |
| 学生3 取自己的文件 | 200 | ✅ 200 |
| 管理员取学生2/3 的文件 | 200 | ✅ 200 / 200 |
| 路径穿越 `../../etc/passwd`（--path-as-is） | 403 | ✅ 403 |
| 路径穿越 URL 编码 `%2e%2e%2f` | 403 | ✅ 403 |
| 不存在的文件 | 404 | ✅ 404 |
| 伪造 token | 401 | ✅ 401 |
| 响应头 | `Cache-Control: private, max-age=300` | ✅ 一致 |

**浏览器回归（Chrome 实测）**：管理端登录 → 打卡记录缩略图与灯箱大图均以 `blob:` URL 正常渲染（`complete=true`），网络面板 `/homework/api/uploads/...` 请求 3 次全部 200 且携带 Authorization。学生端人脸底图走同一指令实现（代码一致）。

**已知功能取舍**：群推送（钉钉/企微）不再附带照片链接（群成员无 token，链接必然 401），`webhook_push_service.py` 的 `photo`/`photo_line` 占位符恒为空，空行由模板渲染自动清理。

### V-04 弱口令清理

- 本地 `.env` 的 `ADMIN_INIT_PASSWORD=admin123` 已置空（留空则 seed 自动生成随机密码并只在容器日志输出一次）；`.env.example` 注释同步强化
- 本地数据库 admin 密码已重置为 16 位随机强密码（**已在整改会话中一次性展示，未写入任何文件**）
- 验证：重置后 `admin123` 登录返回 401；新密码经浏览器实测登录成功
- ⏳ **待办**：生产容器环境变量是否残留 `ADMIN_INIT_PASSWORD=admin123` 及生产库 admin 口令强度，需生产探测后确认（见文末）

### V-06 生产关闭 API 文档

- `main.py`：`PRODUCTION` 环境变量非空时 `docs_url`/`redoc_url`/`openapi_url` 均为 `None`；`deploy.sh` 的 `docker create` 已加 `-e PRODUCTION=1`
- 验证：容器内 `PRODUCTION=1` 时三者均为 `None`；本地（未设）`/docs`、`/openapi.json` 照常 200

### V-01 HTTPS 配置准备（按决策不启用）

- 新增 [`nginx/https.conf.example`](../../nginx/https.conf.example)：完整 443 server 块（TLS1.2/1.3、报告推荐加密套件、会话缓存、OCSP stapling、HSTS）+ 80 端口 ACME 校验与 301 跳转
- 新增 [`nginx/README-HTTPS.md`](../../nginx/README-HTTPS.md)：签发、挂载、续期、回滚全流程；明确 Let's Encrypt 不为裸 IP 签发、HSTS 下发后不可回退等注意事项
- 两个文件均不被现有配置加载，对当前环境零影响
- 注：模板放在 `nginx/` 根目录而非计划原定的 `nginx/sites/`——`sites/*.conf` 被 include 进 default.conf 的 server 块**内部**，放 server 块会导致 nginx 启动失败

### V-03 / V-10 部署脚本 SSH 凭据与主机密钥

- 密钥认证优先：`DEPLOY_SSH_KEY` 存在时走 `ssh -i`，完全不经 sshpass
- 密码回退：`export SSHPASS` + `sshpass -e`，密码不再出现在 argv / `/proc/<pid>/cmdline`
- 主机密钥：`StrictHostKeyChecking=${DEPLOY_SSH_STRICT:-accept-new}`（首次自动记录、指纹变更即拒，防 MITM）
- 全部远程调用（rexec、tar 管道、远程 docker build）统一经单一 `rexec()` 函数，无 `sshpass -p` 残留
- 验证：`bash -n` 语法通过；`SSHPASS=dummy sshpass -e ssh ...` 实测 `ps aux` 输出的命令行不含密码

### V-05 端口绑定收窄

- 本地 `docker-compose.yml`：两服务分别改为 `127.0.0.1:8000:8000` / `127.0.0.1:8001:8000`
- 验证：`docker port` 输出均为 `127.0.0.1:*`；经 Nginx 的 `/homework/`、`/homework/admin/`、`/points/` 全部 200（代理走容器网络，不受影响）
- 生产 `deploy.sh`：新增 `DEPLOY_BIND_ADDR`（默认 `127.0.0.1`）
- ⏳ **待办**：应用到生产前须先探测生产 Nginx upstream 指向（若 Nginx 经宿主 IP 回连则需保持 `0.0.0.0`，见文末）

### V-07 生产 CORS 白名单

- `deploy.sh` 沿用旧容器 `ALLOWED_ORIGINS` 时自动剔除含 `localhost` / `127.0.0.1` 的条目并告警；过滤后为空则中断部署，要求显式提供 `DEPLOY_ALLOWED_ORIGINS`
- 本地 compose 的 `http://localhost` 保留（本地经 Nginx 80 访问的合法 Origin）

### V-08 容器安全加固

本地 compose 两服务均加：`read_only: true`、`tmpfs /tmp:noexec,nosuid,size=100m`、`no-new-privileges`、`cap_drop: ALL`、CPU/内存限额。

**实测发现并修复的坑**：summer-homework 入口脚本以 root 启动修复 `/data` 属主后用 `setpriv` 降权，`cap_drop: ALL` 导致 `setpriv: setresuid failed` 崩溃循环——已通过 `cap_add` 精确保留 5 项能力（CHOWN/FOWNER/DAC_OVERRIDE/SETUID/SETGID，较 Docker 默认 14 项仍大幅收窄）。points-system 全程 root 无降权，无需 cap_add。

验证（`docker inspect`）：

| 项 | summer-homework | points-system |
|----|-----------------|---------------|
| ReadonlyRootfs | true | true |
| CapDrop | [ALL] | [ALL] |
| CapAdd | 5 项 | 无 |
| Memory / CPU | 1G / 2.0 | 1G / 2.0 |
| no-new-privileges | ✅ | ✅ |
| 运行状态 | healthy | healthy |

侧面印证：整改过程中 `docker cp` 因 rootfs 只读被拒绝，加固确实生效。

生产 `deploy.sh` 的 `docker create` 同步加 `--cap-drop ALL` + 同样 5 项 `--cap-add` + 资源限额；`--read-only` 由 `DEPLOY_READONLY_FS=1` 显式开启（生产 bind mount 与本地命名卷不同构，默认关闭待验证）。

### V-11 .secret_key 权限

- `config.py`：写入改为 `os.open(..., 0o600)` 创建即 600（消除先 644 再 chmod 的竞态窗口）；读取分支追加 best-effort `chmod 600` 修复历史遗留
- **额外发现并修复**：`.dockerignore` 原来写 `.secret_key`（不含 `**/`）只匹配构建上下文根目录，导致 `backend/.secret_key` 被烘进镜像层且为 644——已改为 `**/.secret_key`，重建镜像后确认镜像内无该文件
- 宿主 `backend/.secret_key` 已 `chmod 600`（实测 600）
- 本地容器密钥经 `SUMMER_SECRET` 环境变量注入，不落盘
- ⏳ **待办**：生产 `/opt/summer-homework/data/.secret_key` 权限需探测确认

---

## 生产部署交接（由负责人自行执行）

生产服务器的地址与 SSH 凭据不在本机任何配置中留存（`.env` 无 `DEPLOY_*` 变量），经确认生产部署由负责人在服务器上自行执行。完整逐条可粘贴的操作清单见 [PRODUCTION_DEPLOY_CHECKLIST.md](./PRODUCTION_DEPLOY_CHECKLIST.md)，要点：

1. **部署前 3 项只读探测**（在生产服务器执行）：

```bash
# 1. V-05 前置：确认 Nginx upstream 指向（决定生产能否绑定 127.0.0.1）
grep -r 'proxy_pass' /etc/nginx/ 2>/dev/null; docker ps --format '{{.Names}} {{.Ports}}'

# 2. V-04：确认生产容器是否残留弱口令环境变量
docker inspect summer-homework --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -i ADMIN

# 3. V-11：确认生产密钥文件权限
stat -c '%a %U %n' /opt/summer-homework/data/.secret_key
```

2. 部署调用（本机仓库根目录）：`DEPLOY_SSH_HOST=<IP> DEPLOY_SSH_KEY=~/.ssh/id_ed25519 ./scripts/deploy.sh prod`

## 部署提示

下次生产部署（`./deploy.sh prod`）时新配置自动生效，注意：

1. **必须先完成上面第 1 项探测**，若 upstream 非 `127.0.0.1:<port>` 回连，需显式 `DEPLOY_BIND_ADDR=0.0.0.0`
2. 推荐用 `DEPLOY_SSH_KEY=~/.ssh/xxx` 密钥认证；首次连接会自动记录主机指纹（accept-new）
3. 沿用的 CORS 白名单若被过滤为空，需显式 `DEPLOY_ALLOWED_ORIGINS=http://<生产地址>`
4. uploads 认证化会改变学生端/管理端照片加载方式，部署后请立即回归：打卡照片缩略图、灯箱大图、人脸底图
5. 群推送消息自此不再附带照片链接（功能取舍，见 V-02）

---

## 本轮发布前核验（2026-08-03 二次实测）

发布收尾阶段对全部安全项重新实测，结果与整改时一致，另补充以下证据：

| 项目 | 实测结果 |
|------|----------|
| V-02 上传认证化矩阵 | 13/13 通过（旧 `/uploads/` 404、无 token 401、越权 403、路径穿越含 URL 编码 403、伪造 token 401、`Cache-Control: private, max-age=300`）；经 nginx 的 `/homework/api/uploads/` 无 token 同样 401 |
| V-04 弱口令 | `admin123` / `admin` / `123456` / `password` 四个弱口令登录实测均 **401**；容器内 `ADMIN_INIT_PASSWORD` 为空 |
| V-06 API 文档 | `/docs` / `/redoc` / `/openapi.json` 实测均 404；容器内 `PRODUCTION=1` |
| V-08 容器加固 | `read_only` 实测生效（`/app` 写入被拒、`/data` 可写）；`cap_drop=[ALL]`；端口仅绑 `127.0.0.1` |
| V-11 密钥文件 | 宿主 `.secret_key` 权限 **600**；镜像内烘入检查 **0 处**；容器密钥经环境变量注入不落盘 |
| 速率限制 | `RATE_LIMIT_ENABLED=1`；12 次连续错误登录第 3 次即触发 429 熔断（探测用一次性用户名，不影响真实账号） |
| 安全响应头 | 6 项齐全：`X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、CSP、`Referrer-Policy`、`Permissions-Policy`、`X-XSS-Protection` |
| HTTPS | 未启用（按决策）：生效配置中无 443 段、无证书；模板 `nginx/https.conf.example` 就绪 |

注：核验过程中向 `admin` 累计了 4 次登录失败（内存态计数，阈值 5 次/15 分钟）；若核验后立即登录 admin，重启容器可清零。

## 额外安全措施与决策记录（2026-08）

### `/points/` 公网入口已撤销

points-system 后端 12 个接口均无认证，经本地 nginx `/points/` 暴露等于任何人可匿名读写积分数据（实测 `GET /points/api/users` 可匿名返回全部用户）。处置：

- `nginx/sites/points.conf` 两个 location 均改为 `return 403`（附中文说明与恢复前置条件：先给后端加认证层）
- `nginx/default.conf` 根路径导航页移除积分系统入口
- 实测：`/points/`、`/points`、`/points/api/users` 均 403；`/homework/`、`/homework/admin/` 不受影响；本地调试直连 `127.0.0.1:8001` 仍可用

### 悬空项处置决定（经确认）

| 事项 | 决定 | 说明 |
|------|------|------|
| push-config 明文回显推送凭证 | 暂缓 | 掩码需同步改后台保存逻辑，待后续设计确认 |
| 钉钉/企微机器人发送者白名单与 msgId 去重 | 暂缓 | 记录为待处理风险 |
| HTTPS 全站启用 | 暂缓 | 待域名确定，模板已备妥 |
| `PRODUCTION: ${PRODUCTION:-1}` 本地默认开启 | 保留现状 | 本地环境同样关闭文档，无功能损失 |

### 测试数据处置

经确认，本地数据库的测试账户与测试奖品**全部保留**，本轮不做任何删除；且本地库与生产库相互独立，本地数据不会进入生产。生产库经只读盘点（仅 3 个真实用户、无测试账户、无垃圾奖品），**无需清理**。

---

## 生产部署记录（2026-08-03）

- 目标：`192.168.8.155`（rk3528-ddr4），`./scripts/deploy.sh prod`，密码认证（用后已从本机 .env 删除）
- 部署前探测：nginx upstream 为 `127.0.0.1:9000` 回连 → 保持默认 BIND_ADDR；无 ADMIN 环境变量残留；`.secret_key` 已 600（uid 10001）
- 部署前现场备份：`/opt/homework-deploy/deploy-logs/`（fpv.conf + 旧容器环境变量）；数据库文件级快照 `backups/raw_20260803_124043/`
- 迁移：`009_wecom_bot` 自动应用；seed 全部跳过（奖品池/管理员/闯关任务已存在）
- 镜像一致性：running 与 built sha256 相同（1870d2b4b06b）；健康检查 21 秒就绪
- **过程中发现并修复的脚本缺陷**：`deploy.sh` 两处中文全角括号紧贴变量（`$APP_PORT）`、`$SSH_KEY）`），bash 多字节解析下被并入变量名导致 `set -u` 中断；已改为 `${VAR}` + 半角括号，并扫描确认无其他同类隐患
- CORS：旧容器白名单含 localhost，已剔除；显式传入 5 个生产来源（含新 IP 192.168.8.155）

**部署后实测（服务器 + 浏览器）：**

| 项 | 结果 |
|------|------|
| 端口收窄 | `8000/tcp -> 127.0.0.1:9000`；外部直连 9000 连接被拒 ✅ |
| API 文档 | `/docs`、`/redoc`、`/openapi.json` 均 404 ✅ |
| 上传认证化 | 旧 `/uploads/` 404；`/api/uploads/` 无 token 401；浏览器灯箱 33 张照片全部 blob 认证加载成功 ✅ |
| 弱口令 | `admin123` 登录 401 ✅ |
| 容器加固 | CapDrop=[ALL]、no-new-privileges、内存 1G ✅ |
| 数据完整 | users 3 / prizes 14 / checkins 16 / redemptions 1 / challenge_tasks 8 / push_logs 18 / uploads 19 文件，与部署前一致 ✅ |
| 管理端 | 奖品管理 14 行 + 分页信息；"新增奖品"弹窗正常开合 ✅ |
| 学生端 | 打卡记录"第 1/4 页 · 共 16 条"，翻页到第 2/4 页正常；商城/抽奖 tab 切换正常；控制台零报错 ✅ |
| nginx | `/homework/`、`/homework/admin/`、`/homework/api/health` 经 80 端口全部 200；旧 `/homework/uploads/` 段 404（预期，前端已改走 `/api/uploads/`）✅ |
