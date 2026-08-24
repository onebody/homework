# 工作区阶段性总结报告

> hanghang_WS 工作区 · 项目全周期总结
> 更新时间：2026-08-24 · 主线版本：summer-homework-checkin v1.6.0（宠物乐园·多宠物领养 + 改名 + Emoji 修复）

---

## 一、工作区总览

本工作区为家庭学习场景自研项目集合，以暑假作业打卡系统为核心，已完成从需求分析、架构设计、功能开发、安全加固到双环境部署上线的完整交付闭环。

| 项目 | 定位 | 技术栈 | 仓库状态 | 当前状态 |
| --- | --- | --- | --- | --- |
| summer-homework-checkin | 暑假作业打卡系统（核心） | FastAPI + SQLite + Vue3 | 入库 | ✅ 双环境运行（本地+生产） |

---

## 二、核心项目进展

### 2.1 summer-homework-checkin（暑假作业打卡系统）

面向三年级小学生的「暑假日常作业学习打卡」全周期管理系统，三端角色（学生 H5 / 家长 / 管理后台）。

**功能迭代主线**：

| 版本 | 里程碑 | 达成情况 |
| --- | --- | --- |
| v0.9 一期 · 基础闭环 | 打卡/补卡/审核/连续统计/抽奖/奖品/家长绑定/报表全链路 | ✅ |
| v1.0 二期 · 体验重构 | 学生端 5 主菜单重构、打卡闯关合并页、转盘抽奖、文档体系 | ✅ |
| v1.1 三期 · 管理增强 | 管理后台仪表盘（8 指标卡片 + Chart.js 三图表 + 快捷操作） | ✅ |
| v1.2 四期 · 安全加固 | 安全审计修复、敏感信息全库清理、`.gitignore` 门禁体系 | ✅ |
| v1.3 五期 · 集成与治理 | Webhook 推送（钉钉/企微）、钉钉双向机器人、时区治理、站点动态配置 | ✅ |
| v1.3.1 推送治理 | 推送模板三轮修复、后台数据概览统计修复、站点积分配置 | ✅ |
| v1.3.2 六期 · 安全深化 | 渗透测试 17 项全量整改、企微智能机器人（回调双向）、图片自动压缩、微信浏览器兼容、前端 CDN 本地化 | ✅ |
| v1.4 七期 · 宠物乐园 | 宠物领养/喂养/成长/形态进化/图鉴/道具商店 | ✅ |
| v1.5.0 八期 · 生态反馈 | 食物适配性校验、生病机制、连击加成、适配性矩阵、安全检测 9.2/10 | ✅ |
| v1.6.0 九期 · 多宠物 | 多宠物领养（最多 3 只）、宠物改名、种类 Emoji 修复 | ✅ 最新 |

**Alembic 迁移链**（当前 `012_pet_suitability`）：
`001 初始 → 002 推送双向 → 003 北京时间治理 → 004 站点标语 → 005 闯关推送 → 006 推送模板 → 007 模板种子 → 008 站点积分 → 009 企微智能机器人 → 010 宠物系统 → 011 食物商店 → 012 适配性校验`

**安全加固进展**（安全评估识别的 17 项风险 V-01~V-17 全量整改，详见整改报告）：

- 上传目录认证化：移除 `/uploads` 公开挂载，改为 `/api/uploads` Token 认证 + 签名 URL（兼容 `<img>` 与 webhook 链接）；
- 容器加固：根文件系统只读、`cap_drop ALL` + 五项最小能力、no-new-privileges、CPU/内存限额；
- SSH 凭据安全：deploy.sh 改用 `sshpass -e` 环境变量传递，杜绝 argv 泄露；
- 生产 `PRODUCTION=1` 关闭 /docs、/redoc、/openapi.json；
- 速率限制、CORS 收窄、端口仅绑定 loopback、密钥文件权限收敛。

---

## 三、关键技术决策

### 3.1 前端第三方库本地化（vendoring）取代 CDN

- **背景**：学生端/管理端硬编码 `cdn.jsdelivr.net` 的 Vue/Chart.js，国内网络不可达（`ERR_CONNECTION_CLOSED` → `Vue is not defined` 白屏），且与 CSP 白名单不一致。
- **决策**：评估后选择**自托管**而非「动态 CDN 配置」——将 Vue 3.5.41（`vue.global.prod.js`）与 Chart.js 4.5.1（`chart.umd.min.js`）收入 `frontend/vendor/`，由后端以 `StaticFiles` 挂载 `/vendor` 路由同源提供（挂载顺序先于 `/`）。
- **收益**：供应链风险消除、离线/内网可用、无区域封锁、CSP 可完全收紧；产物随 Docker 镜像打包，版本以 `?v=` 参数管理缓存。

### 3.2 CSP 收紧至同源

`Content-Security-Policy` 移除全部外部 CDN 域名，收紧为：
`default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'`
（`'unsafe-eval'` 为 Vue 运行时编译 DOM 模板的最小必要放行）。

### 3.3 Docker 安全加固

- 根文件系统只读 + tmpfs（本地 Compose）；生产以 bind mount + 非 root（appuser uid 10001）运行；
- `cap_drop: ALL`，仅保留 setpriv 降权所需的 CHOWN/FOWNER/DAC_OVERRIDE/SETUID/SETGID 五项；
- `no-new-privileges`、CPU 2 核 / 内存 1G 限额、健康检查内置；
- 端口全部仅绑定 `127.0.0.1`（本地直连 8003/8001，生产 9000），外部访问统一经 Nginx。

### 3.4 子路径部署适配

- 前端全相对路径：学生端 `./vendor/...`、管理端 `../vendor/...`，兼容 `/`、`/admin/`、`/homework/`、`/homework/admin/` 四种形态；
- `app.js` 内 `BASE_PATH` 正则自动检测子路径并为 API 请求加前缀；
- Nginx 以 `rewrite ^/homework/(.*)$ /$1 break` 剥离前缀后代理到容器。

### 3.5 面向生产的部署脚本设计

- SQLite WAL 一致性快照备份（`sqlite3.backup` API，回退为含 -wal/-shm 的文件级拷贝）；
- 健康检查轮询（默认 180s，替代早期固定 10s 误判）；
- CORS 白名单未显式指定时**沿用现有容器值**并自动剔除 localhost 来源，避免抹掉线上公网入口；
- systemd 托管探测（避免 docker rm 与看门狗竞争）、镜像一致性校验（running 与 built 哈希比对）。

### 3.6 其他关键决策（延续）

- **单行配置表模式**（SiteConfig/PushConfig）：后台配置即改即生效，无需重启；
- **异步推送解耦**：daemon 线程 + 独立会话，推送故障绝不影响打卡主链路；
- **时区统一 naive 北京时间**：`timeutil.now_local()` 单一入口 + Dockerfile `TZ=Asia/Shanghai` 双保险；
- 迁移优先于重建：历史数据一律 Alembic 平移，升级零丢失。

### 3.7 项目精简（2026-08-24）

为聚焦核心业务，已将以下独立项目从版本库移除（保留本地副本）：
- `points-system/` — 积分兑换系统
- `2048/` — 2048 数字合并游戏
- `snake-game/` — 贪吃蛇大冒险游戏
- `homework-monorepo/` — 早期归档副本

上述项目已加入 `.gitignore`，不再随业务代码入库。

---

## 四、已验证的部署流程

### 4.1 本地 Docker 测试环境（`./scripts/deploy.sh local`）

备份数据卷 → `docker compose up -d --build`（保留数据卷）→ 容器启动自动执行 Alembic 迁移 → 轮询 `http://127.0.0.1:8003/api/health`。
最近一次验证（2026-08-14）：health 200、迁移至 `009_wecom_bot`、nginx 子路径（7765）200、浏览器端到端 Vue 3.5.41 / Chart.js 4.5.1 挂载无控制台错误。

### 4.2 生产服务器 192.168.8.155（`DEPLOY_SSH_HOST=192.168.8.155 ./scripts/deploy.sh prod`）

WAL 快照备份 → tar 管道传输代码（`COPYFILE_DISABLE=1` 防 AppleDouble）→ 服务器构建镜像 → systemctl/docker 停旧删旧 → 校验 `.secret_key` → chown 适配非 root → 新镜像创建容器（加固参数齐全）→ 180s 轮询健康检查 → 镜像一致性校验。
最近一次验证（2026-08-14）：

| 验证项 | 结果 |
| --- | --- |
| `http://192.168.8.155/homework/api/health` | 200（启动后 18s 就绪） |
| 数据库迁移 | `009_wecom_bot`（最新） |
| 镜像一致性 | running == built（sha256:b8a7cf64） |
| CORS 白名单 | 沿用现有（含 155:9000 / 公网入口），无覆盖丢失 |
| vendor 本地托管资源 | `/homework/vendor/` 下 Vue/Chart.js 均 200 |
| CSP 响应头 | 已收紧生效（script-src 'self'） |
| 9000 端口外部不可达 | 符合预期（仅绑定 127.0.0.1，安全加固设计） |

---

## 五、遗留问题与后续优化建议

| # | 遗留问题 | 建议 |
| --- | --- | --- |
| 1 | CORS 白名单中公网来源 `http://115.206.235.46:7765` 当前探测不可达（疑似动态公网 IP 变化） | 确认最新公网 IP 后经 `DEPLOY_ALLOWED_ORIGINS` 更新；若已废弃则收窄白名单 |
| 2 | HTTPS 尚未启用（无域名，生产为 HTTP 内网访问） | 申请域名 + Let's Encrypt 证书，沿用已预备的 `nginx/https.conf.example` |
| 3 | 人脸识别在无外网沙箱降级运行 | 生产环境联网后复验人脸链路，补充真实人脸样本回归 |
| 4 | 本地 `venv` 损坏（直跑开发改用系统 python3） | 重建虚拟环境并同步 requirements |
| 5 | 钉钉 Outgoing Token 回调需公网可达，内网部署下不可用 | 与 HTTPS/公网入口一并解决 |

**后续优化方向**：前端构建化（Vite 打包替代 CDN 运行时，消除 `unsafe-eval`）、SQLite → PostgreSQL 演进评估（并发增长后）、管理后台操作审计日志、备份定期异地同步。

---

## 六、测试与验证体系

- **API 边界测试**：新增接口覆盖默认值/401/400/置空恢复/部分更新用例；
- **浏览器端到端**：chrome-devtools 自动化断言（Vue/Chart 加载、应用挂载、控制台零错误），学生端/管理端双端覆盖；
- **迁移验证**：「基线计数 + 时间样本 → 部署 → diff」法，生产数据零丢失；
- **部署回归**：每次部署后执行 health 200、页面 200、认证链路 401、静态资源版本号核对；
- **安全验证**：13 项 curl 验证矩阵（旧挂载 404、无 token 401、越权 403、路径穿越 403、伪造 token 401 等）。

---

## 七、代码质量与仓库治理

- 分层清晰：routers（协议）/ services（业务）/ utils（工具），业务逻辑不散落路由；
- 时间处理收敛单一入口 `timeutil.now_local()`；迁移脚本防御式编写、双向可逆；
- `.gitignore` 门禁体系：密钥/数据库/上传/备份/日志/临时文件全类目拦截，历史敏感信息已全库清理；
- 文档随代码同步演进（docs/ 8 份文档 + 根 README + repowiki），每版本更新 CHANGELOG；
- 渗透测试与安全整改报告归档于 `docs/`（SECURITY_REMEDIATION_REPORT.md 等），整改项可追溯。

---

> 相关文档：[架构设计](ARCHITECTURE.md) · [功能模块](FEATURES.md) · [API 接口](API.md) · [部署运维](DEPLOYMENT.md) · [变更记录](CHANGELOG.md) · [安全整改报告](SECURITY_REMEDIATION_REPORT.md)
