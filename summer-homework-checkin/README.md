# 暑假作业打卡登记系统（三年级）

面向三年级小学生的「暑假日常作业学习打卡」全周期管理系统。采用**前后端分离架构**，技术栈 **Python + FastAPI + Vue**，学生端以 **H5** 形式适配手机/平板，后台管理通过**独立外部页面**承载。

💡 **最新版本 v1.0** — 学生端菜单重构（打卡闯关合并页 + 独立转盘抽奖）与项目文档体系，详见[版本记录](#八版本记录)。

📚 **完整文档**：见 [`docs/`](docs/README.md) —— [架构设计](docs/ARCHITECTURE.md) · [功能模块](docs/FEATURES.md) · [API 接口](docs/API.md) · [部署运维](docs/DEPLOYMENT.md) · [用户手册](docs/USER_GUIDE.md) · [变更记录](docs/CHANGELOG.md)。

---

## 一、功能与需求对应

| 需求 | 实现 |
| --- | --- |
| 每日仅 1 次有效打卡 | `checkin_service` 校验同一自然日仅允许 1 条正常打卡 |
| 强制上传现场照片 + 精确记录 | 打卡流程序言上传照片，系统记录公历日期、精确时间、照片素材 |
| 连续打卡天数自动统计 | `recompute_and_grant` 基于有效打卡日期计算当前/最长连续天数 |
| 补卡功能（每月≤3次 + 凭证） | `makeup` 类型打卡，限额可配（环境变量 `MAX_MAKEUP_PER_MONTH`），需额外凭证 |
| 防代打卡 | 四重校验：①照片真实性/尺寸 ②地理位置一致性（距常用位置超阈值标记风险）③**人脸 1:1 本人比对**（默认 insightface，部署环境联网即生效；沙箱无网自动降级安全模式）④场景合规综合判定 |
| 7 天解锁抽奖资格 | 连续有效打卡每满 7 天自动 +1 资格，永久累积、不可折现/转让 |
| 抽奖（加权随机） | `lottery_service` 按概率与库存加权抽取 |
| 奖品管理（预设池 + 自定义） | 内置 12 项三年级适配奖品（文具/户外/兴趣），支持增删改、概率/库存/上下架 |
| 家长绑定 + 通知 | 家长凭孩子绑定码绑定，打卡/抽奖实时通知家长 |
| 家长解绑孩子 | 家长端可解绑已绑定的孩子，解绑后可重新绑定其他孩子 |
| 密码修改 | 学生/家长/管理员均可通过「旧密码→新密码」修改登录密码 |
| 全局回车提交 | 所有表单支持回车键快捷提交，提升操作效率 |
| 速率限制 | 登录/注册接口限频（默认 10 次/分钟登录，5 次/分钟注册），防暴力破解 |
| 数据存储与报表 | SQLite 永久存储；暑假全周期可视化学习报告（频率/最长连续/完成情况），可打印下载 |
| H5 卡通清新 + 3 步内操作 | Vue3 单页，底部导航，打卡 3 步完成 |
| 后台独立管理页 | `/admin` 独立页面：概览、奖品全生命周期、用户、打卡（含位置异常） |

---

## 二、目录结构

```
summer-homework-checkin/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（路由挂载 + 静态托管）
│   │   ├── config.py          # 配置（阈值、窗口、限额，支持环境变量覆盖）
│   │   ├── database.py        # SQLAlchemy 引擎/会话
│   │   ├── models.py          # ORM 模型
│   │   ├── schemas.py         # Pydantic 模型
│   │   ├── security.py        # 密码哈希 + 签名 Token
│   │   ├── deps.py            # 鉴权依赖
│   │   ├── routers/           # auth/checkin/lottery/prize/redeem/parent/report/admin/challenge/face
│   │   ├── services/          # 打卡/抽奖/通知/校验/人脸/报表 业务逻辑
│   │   └── utils/             # geo(距离) / storage(上传) / image(图像解析) / rate_limit(速率限制)
│   ├── uploads/               # 上传照片（运行时生成，已 gitignore）
│   ├── seed.py                # 种子数据（预设奖品池 + 管理员）
│   ├── requirements.txt
│   └── app.db                 # SQLite 数据库（运行时生成）
└── frontend/
    ├── student/               # H5 学生端（Vue3 CDN，免构建）
    └── admin/                 # 独立后台管理页（Vue3 CDN，免构建）
├── tests/                     # 回归测试套件（71 个测试，覆盖所有核心功能）
│   ├── test_auth.py           # 认证模块（注册/登录/密码修改）
│   ├── test_checkin.py        # 打卡模块
│   ├── test_admin_review.py   # 管理审核模块
│   ├── test_parent.py         # 家长模块（绑定/解绑/代打卡）
│   ├── test_mall.py           # 商城/抽奖模块
│   ├── test_challenge.py      # 闯关任务模块
│   ├── test_report.py         # 报表模块
│   ├── test_face.py           # 人脸模块
│   ├── test_utils.py          # 共享测试工具
│   ├── run_all.py             # Python 运行器
│   └── run_tests.sh           # Shell 运行器
```

---

## 三、快速开始

### 1. 后端
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py                 # 建表 + 写入预设奖品 + 创建管理员
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
默认管理员账号：**admin**（首次启动时自动生成随机密码，见控制台输出；或通过 `ADMIN_INIT_PASSWORD` 环境变量指定）

> 测试/运维可调：补卡月限额 `MAX_MAKEUP_PER_MONTH=10 uvicorn ...`；地理阈值 `GEO_THRESHOLD_METERS=1500`；人脸识别相似度阈值 `FACE_MATCH_THRESHOLD=0.4`（越高越严格）；已采集底图后的人脸策略 `FACE_MODE_ON_ENROLLED=enforce`（enforce=不通过则拒绝打卡 / soft=仅标记风险）；速率限制 `RATE_LIMIT_ENABLED=0 uvicorn ...`（0=关闭）。

### 2. Docker 部署
```bash
# 从项目根目录执行
cd ..  # 回到 hanghang_WS/
docker compose up -d --build summer-homework
# 访问 http://localhost:8000/
```
也可使用一键部署脚本：
```bash
bash scripts/deploy.sh local    # 本地部署（保留数据，增量更新）
bash scripts/deploy.sh prod     # 生产部署（自动备份 DB + 远程构建）
```

### 2. 前端（免构建，浏览器直接访问）
- 学生 H5：`http://<服务器>/` （手机浏览器打开，适配移动端）
- 后台管理：`http://<服务器>/admin/`

学生端注册后，在「我的」查看**绑定码**，发给家长；家长端注册后凭绑定码绑定孩子，即可接收通知。

### 3. 启用人脸识别（推荐，防代打卡核心）
默认人脸后端为 insightface。**有外网的机器无需额外操作**：首次调用采集/打卡接口时自动下载 buffalo_l 模型（约 340MB，存于 `~/.insightface`）后即生效。可调参数：
- `FACE_MATCH_THRESHOLD=0.4`（余弦相似度阈值，越高越严格）
- `FACE_MODE_ON_ENROLLED=enforce`（已采集底图后人脸不通过则**拒绝打卡**）/ `soft`（仅标记风险）
- 无外网环境会自动降级为安全模式（见第五节说明），整体链路仍可运行与演示。

---

## 四、核心 API 概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` `/api/auth/login` | 注册/登录（student/parent） |
| PUT | `/api/auth/password` | 修改密码（旧密码→新密码） |
| POST | `/api/checkin` | 打卡（照片+位置+补卡凭证） |
| GET | `/api/checkin/streak` | 连续天数/抽奖券/今日状态 |
| POST | `/api/lottery/draw` | 抽奖（消耗 1 资格） |
| GET/POST/PUT/DELETE | `/api/admin/prizes[/id]` | 奖品全生命周期管理 |
| POST | `/api/parent/bind` | 家长绑定孩子 |
| DELETE | `/api/parent/unbind/{student_id}` | 家长解绑孩子 |
| GET | `/api/parent/child-report/{id}[/html]` | 家长查看孩子报表（JSON/HTML） |
| POST/GET/DELETE | `/api/face/enroll` `/api/face/status` | 人脸底图采集/状态/撤销（1:1 比对基准） |
| GET | `/api/report/me/html` `/api/parent/child-report/{id}/html` | 可视化学习报告 |

---

## 五、防代打卡机制说明

系统以「**真实本人打卡**」为目标，当前实现四重校验：

1. **照片真实性**：校验文件为合法 JPEG/PNG、体积与最小边长门槛，过滤占位图/缩略图（见 `utils/image.py`）。
2. **地理位置一致性**：拍照获取设备经纬度，与账号常用位置比对，超出阈值（`GEO_THRESHOLD_METERS`）标记 `geo_flag`，后台红色高亮。
3. **人脸 1:1 本人比对（核心防代打卡）**：学生账号在「我的」采集一张正脸底图（`/api/face/enroll`）；每次打卡实时拍摄的现场照与该底图经 insightface（buffalo_l）提取 512 维特征并做余弦相似度比对，低于阈值（`FACE_MATCH_THRESHOLD`，默认 0.4）直接**拒绝打卡**，从根源防止他人代打卡。模型首次运行时按需从官方源下载至 `~/.insightface`（**需联网**；无外网环境自动降级，见下文）。
4. **场景合规综合判定**：以上结果综合为 `scene_check` 与 `risk` 等级，打卡记录持久化 `face_status` / `face_score` / `face_flag` 供后台追溯。

> 模式说明：当前为 **1:1 本人比对**（一个孩子 vs 自己的底图），数据模型已预留 `face_embedding` 等字段，未来可平滑扩展为 1:N（从全班人脸库检索身份），业务主流程无需改动。

> **关于开发与部署环境的人脸识别**：默认后端为 insightface，在**能访问外网的部署机器**上首次运行会自动下载人脸模型并启用真实 1:1 比对。**WorkBuddy 沙箱等无外网下载权重的环境会自动降级为安全模式**——模型缺失时，已采集底图的账号打卡将被拒绝以防绕过，未采集账号正常；采集 / 比对 / 拦截链路仍然完整可演示。要启用真实识别，仅需保障外网或预置模型，业务代码无需改动。

---

## 六、测试与验收

- **回归测试套件**（`tests/`）：71 个自动化测试，覆盖认证/打卡/审核/家长/商城/闯关/报表/人脸 8 大模块。
  - 运行方式：`python -m pytest tests/ -v`（本地）或 `bash tests/run_tests.sh`（自动检测依赖）
  - 支持多环境：`API_BASE_URL=http://192.168.1.112:6565 python -m pytest tests/ -v`
- **真人测试建议**：邀请 3–5 名三年级小学生，在手机端独立完成「注册 → 打卡 → 抽奖 → 查看报告」全流程（均可在 3 步内完成）。

---

## 七、生产部署建议

- 数据库：SQLite 适合演示；正式环境建议替换为 PostgreSQL/MySQL 并配置连接池。
- 服务：uvicorn 多 worker（`--workers N`）或前置 Nginx；静态资源可托管至对象存储/CDN。
- 通知：当前为站内通知；可扩展接入短信/微信模板消息（在 `notify_service` 增加渠道即可）。
- 人脸比对：默认 insightface 本地推理（首次运行自动下载 buffalo_l，需外网）；无外网环境自动降级为安全模式（已采集底图则拒绝打卡防绕过）。若要更高精度或多用户 1:N，可重写 `services/face_service.py` 后端（已预留 `face_embedding` 等字段）。

---

## 八、版本记录

### v1.0（2026-07）
- **新增**：学生端底部导航重构为 5 主菜单（🏠 首页 / 📝 打卡闯关 / 🎰 抽奖 / 🛍️ 商城 / 👤 我的）
- **新增**：「打卡闯关」合并页，页内子 tab 切换（📸 每日打卡 / 🏆 闯关任务）
- **新增**：独立「抽奖」主菜单 —— `conic-gradient` 彩色转盘、5 圈精准落点动画、抽奖券展示与中奖记录
- **新增**：项目文档体系（`docs/`）—— 架构 / 功能 / API / 部署 / 用户手册 / 变更记录
- **改进**：tabbar 图标+文字纵向堆叠，`env(safe-area-inset-bottom)` 全面屏适配、窄屏字号自适应

### v0.9（2026-07-08）
- **新增**：密码修改（所有角色通用，旧密码→新密码）
- **新增**：家长端解绑孩子（DELETE `/api/parent/unbind/{student_id}`），解绑后可重新绑定
- **新增**：全局回车提交，所有表单支持 Enter 快捷操作
- **新增**：速率限制器（登录 10 次/分钟、注册 5 次/分钟），防暴力破解
- **改进**：管理员默认密码通过 `ADMIN_INIT_PASSWORD` 环境变量指定，未设置时自动生成随机密码
- **改进**：回归测试全面重构 — 8 个独立模块、71 个测试用例；支持多环境（本地/生产）运行
- **修复**：纯色 JPEG 照片因体积过小被服务器拒绝的问题
- **修复**：测试中的速率限制冲突（通过 `RATE_LIMIT_ENABLED=0` 环境变量关闭）
