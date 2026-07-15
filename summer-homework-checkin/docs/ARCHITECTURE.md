# 架构设计文档

> 暑假作业打卡系统（三年级）· 架构与技术选型说明
> 版本：v1.0 ｜ 最近更新：2026-07

---

## 一、系统概览

面向小学三年级学生的「暑假日常作业学习打卡」全周期管理系统，采用**前后端分离**架构，一个后端服务同时托管三端页面：

| 端 | 访问路径 | 使用者 | 形态 |
| --- | --- | --- | --- |
| 学生端 H5 | `/` | 学生 / 家长 | Vue3（CDN 免构建）移动端单页 |
| 后台管理 | `/admin/` | 管理员（老师） | Vue3（CDN 免构建）桌面端单页 |
| 上传资源 | `/uploads/` | 全部 | 静态文件（打卡照片/人脸底图） |

配套还有一个独立的**打卡积分兑换系统**（`points-system`），通过 `docker-compose` 与主系统并列部署（端口 8001）。

---

## 二、技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 后端框架 | FastAPI | 异步 Web 框架，自带 OpenAPI 文档 |
| ORM | SQLAlchemy | 声明式模型，`models.py` 定义 9 张表 |
| 数据库 | SQLite | 零配置、单文件、可持久化；生产可平滑替换为 PG/MySQL |
| 认证 | 自实现签名 Token | HMAC 签名 + 每用户随机盐哈希密码（`security.py`） |
| 人脸识别 | insightface（buffalo_l） | 1:1 本人比对，512 维向量余弦相似度；无外网自动降级 |
| 前端 | Vue 3（global.prod CDN） | 免构建，浏览器直接运行 |
| 部署 | Docker + docker-compose | 多阶段镜像；数据卷持久化 |
| 反向代理 | Nginx（可选） | 支持 `/homework/` 子路径部署 |

---

## 三、分层架构

```
┌─────────────────────────────────────────────────┐
│  前端层（Vue3 CDN 免构建）                        │
│  student/  (H5 学生+家长端)   admin/ (后台管理)    │
│  · BASE_PATH 自动检测，适配子路径部署              │
│  · fetch 封装 api()，统一注入 Bearer Token         │
└───────────────────────┬─────────────────────────┘
                        │ HTTP / JSON + multipart
┌───────────────────────▼─────────────────────────┐
│  接入层（FastAPI）                                │
│  · CORSMiddleware（白名单来源）                    │
│  · rate_limit 中间件（登录/注册限频）              │
│  · 静态挂载：/uploads /admin /（student）          │
└───────────────────────┬─────────────────────────┘
┌───────────────────────▼─────────────────────────┐
│  路由层（routers/）                               │
│  auth checkin lottery prize parent report        │
│  admin face redeem challenge                     │
│  · deps.py 鉴权依赖（角色校验）                    │
└───────────────────────┬─────────────────────────┘
┌───────────────────────▼─────────────────────────┐
│  服务层（services/）—— 业务逻辑                    │
│  checkin  抽奖  通知  校验  人脸  兑换  报表  闯关  │
└───────────────────────┬─────────────────────────┘
┌───────────────────────▼─────────────────────────┐
│  数据层（SQLAlchemy + SQLite）                    │
│  models.py（ORM）  database.py（引擎/会话）        │
│  utils/ geo · storage · image · rate_limit        │
└─────────────────────────────────────────────────┘
```

---

## 四、后端目录职责

```
backend/app/
├── main.py          # 入口：中间件、路由挂载、静态托管、健康检查
├── config.py        # 全部配置项（阈值/窗口/限额），支持环境变量覆盖
├── database.py      # SQLAlchemy 引擎与会话
├── models.py        # 9 张 ORM 表
├── schemas.py       # Pydantic 出入参模型
├── security.py      # 密码哈希（每用户盐）+ HMAC 签名 Token
├── deps.py          # 鉴权依赖（当前用户 / 角色校验）
├── routers/         # HTTP 路由（薄层，仅参数与鉴权）
│   ├── auth.py         认证：注册/登录/我的信息/改密码
│   ├── checkin.py      打卡：提交/今日/连续/历史
│   ├── lottery.py      抽奖：券数/抽奖
│   ├── prize.py        奖品：查询 + 管理端 CRUD
│   ├── redeem.py       商城：积分兑换/替换
│   ├── parent.py       家长：绑定/解绑/代打卡/代兑换/通知/报表
│   ├── admin.py        管理：统计/用户/打卡审核/兑换审核
│   ├── challenge.py    闯关：任务/打卡/管理端任务管理
│   ├── report.py       报表：JSON + HTML 可视化
│   └── face.py         人脸：采集/状态/撤销
├── services/        # 业务逻辑（可测、无 HTTP 依赖）
│   ├── checkin_service.py       打卡校验、连续天数计算、积分/抽奖发放
│   ├── lottery_service.py       加权随机抽奖 + 中奖建单
│   ├── redeem_service.py        积分兑换、抽奖券兑换、替换
│   ├── verification_service.py  照片/地理/人脸综合风险判定
│   ├── face_service.py          insightface 特征提取与比对（降级安全模式）
│   ├── challenge_service.py     闯关任务与打卡
│   ├── report_service.py        学习报告聚合
│   └── notify_service.py        站内通知（学生/家长）
└── utils/           # 通用工具
    ├── geo.py          经纬度距离（Haversine）
    ├── storage.py      上传落盘 + public_url 生成
    ├── image.py        图片合法性/尺寸校验
    └── rate_limit.py   内存滑动窗口限频
```

---

## 五、关键设计决策

### 5.1 单后端多端托管
FastAPI 通过 `StaticFiles(html=True)` 直接托管学生端与管理端，学生端挂载在根路径 `/`，避免额外的前端服务器。前端全部使用 Vue3 CDN 版本，**免构建**，降低部署与维护复杂度。

### 5.2 子路径部署适配（BASE_PATH）
前端 `app.js` 通过 `window.location.pathname` 自动检测 `/homework` 前缀，动态推导 `BASE_PATH`，所有 API 请求与上传资源 URL 都基于它拼接；静态资源引用统一使用相对路径（`./app.js`、`./student.css`）。因此同一份代码既能在根路径运行，也能在 Nginx `/homework/` 反向代理下运行，无需改代码。

### 5.3 冗余统计字段
`User` 表内置 `current_streak / longest_streak / effective_checkins / lottery_tickets / points` 等冗余统计字段，由 `checkin_service.recompute_and_grant` 在每次有效打卡后重算并落库，读取时零计算、直接返回，换取查询性能。

### 5.4 积分与抽奖并行的激励体系
- **积分**：每次打卡自动获得（正常 +10 / 补卡 +5），用于「积分商城」兑换实物奖品。
- **抽奖资格**：连续有效打卡每满 7 天自动 +1，永久累积，用于「转盘抽奖」。
- 二者互不冲突：奖品池中 `is_lottery_ticket=True` 的条目为「抽奖券」，用积分兑换后增加抽奖资格，形成积分→抽奖的转化闭环。

### 5.5 防代打卡四重校验
打卡提交时由 `verification_service` 综合判定：①照片真实性 ②地理位置一致性 ③人脸 1:1 本人比对 ④场景合规。结果持久化到 `CheckIn.scene_check / face_status / face_score / geo_flag`，供后台审核追溯。详见[功能模块说明](FEATURES.md#四防代打卡机制)。

### 5.6 家长双角色代理
家长账号通过绑定码关联多个孩子，家长端所有操作（打卡/兑换/抽奖/报表）都带 `child_id`，走 `/api/parent/*` 系列端点，在服务层校验绑定关系后代孩子执行。前端以 `actingChildId` 表示当前操作对象。

---

## 六、数据流示例：一次打卡

```
学生端上传照片(+位置)
   │  POST /api/checkin  (multipart)
   ▼
checkin.py 校验登录 → 落盘照片(storage)
   │
   ▼
verification_service 综合校验
   ├─ image.py     照片合法性/尺寸
   ├─ geo.py       与常用位置距离 → geo_flag
   └─ face_service 现场照 vs 底图 512 维余弦 → face_status/score
   │  (enforce 模式下人脸不通过直接拒绝)
   ▼
checkin_service 写入 CheckIn（review_status=pending）
   │  recompute_and_grant：重算连续天数
   │  满 7 天 → lottery_tickets +1；发放积分
   ▼
notify_service 通知家长
   ▼
返回今日状态 / 连续天数 / 抽奖券
```

---

## 七、部署拓扑（docker-compose）

```
                    ┌──────────────────────────┐
   :8000 ───────────▶ summer-homework 容器      │
                    │  FastAPI + 学生端 + 管理端 │
                    │  卷 summer-data:/data      │
                    │   ├─ app.db（SQLite）      │
                    │   └─ uploads/（照片/人脸）  │
                    └──────────────────────────┘
                    ┌──────────────────────────┐
   :8001 ───────────▶ points-system 容器        │
                    │  积分兑换系统              │
                    │  卷 points-data:/data      │
                    └──────────────────────────┘
```

数据库与上传目录通过环境变量 `DB_PATH=/data/app.db`、`UPLOAD_DIR=/data/uploads` 重定向到命名卷，实现跨容器重建的数据持久化。详见[部署运维指南](DEPLOYMENT.md)。
