---
name: fastapi-vue-fullstack-dev
description: 轻量全栈项目标准化开发流程，覆盖 FastAPI 后端、Vue3 CDN 前端、SQLite/Alembic 数据库、Docker 容器化与生产部署的完整链路（需求分析→架构设计→编码→安全加固→测试→部署上线）。当用户要新建或迭代 FastAPI/Vue3/SQLite 技术栈的 Web 项目、设计数据库迁移、编写部署脚本、做安全加固或生产发布时使用。
---

# FastAPI + Vue3 轻量全栈开发流程

从真实生产项目（暑假作业打卡系统）沉淀的标准化开发流程，适用于中小型全栈 Web 应用：管理后台 + 用户端 + REST API + 单机 Docker 部署。

## 技术栈基线

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | FastAPI + SQLAlchemy + Pydantic | 类型安全、自动文档、轻量 |
| 数据库 | SQLite（WAL 模式）+ Alembic 迁移 | 零配置、单文件、够用即好 |
| 前端 | Vue3 CDN 引入，无构建步骤 | 免打包链路，改完即生效 |
| 部署 | Docker + docker compose + Nginx 子路径反代 | 单机可控、数据卷持久化 |
| 认证 | 自签 JWT（HMAC）+ 角色依赖注入 | 无外部依赖 |

## 开发全流程

复制此清单跟踪进度：

```
项目进度：
- [ ] 阶段1：需求分析 — 产出结构化需求提示词文档
- [ ] 阶段2：架构设计 — 分层目录 + 数据模型 + API 契约
- [ ] 阶段3：数据库 — 模型 + 防御式迁移 + 幂等种子数据
- [ ] 阶段4：后端实现 — router → service → model 分层
- [ ] 阶段5：前端实现 — 相对路径 + 响应式 + 版本号刷新
- [ ] 阶段6：安全加固 — 密钥/CORS/速率限制/上传校验
- [ ] 阶段7：测试验证 — 按模块回归测试 + 浏览器冒烟
- [ ] 阶段8：部署上线 — 本地 Docker 验证 → 生产增量发布
```

### 阶段1：需求分析

先写结构化需求文档再动手。固定九段式结构（业务规则 → 数据模型 → API 设计 → 业务逻辑 → 前端实现 → 移动端适配 → 安全性要求 → 验收标准 → 文件清单）。提示词模板见 [prompts.md](prompts.md)。

要点：
- 状态流转必须画出来（如 `pending → fulfilled | rejected`），并明确每个状态的触发者
- 验收标准写成可勾选的 checklist，完成一项勾一项
- 文件清单预先列出要动的文件及其状态（已完成/待补充）

### 阶段2：架构设计

标准分层目录（前后端同仓，后端直接挂载前端静态目录）：

```
project/
├── backend/
│   ├── app/
│   │   ├── config.py      # 全部环境变量在此收口（DB_PATH/UPLOAD_DIR/SECRET…）
│   │   ├── database.py    # engine + SessionLocal + Base
│   │   ├── models.py      # SQLAlchemy 模型（单文件，中小项目够用）
│   │   ├── schemas.py     # Pydantic 入/出参
│   │   ├── security.py    # 密码哈希 / JWT / 敏感数据加密
│   │   ├── deps.py        # get_current_user / require_role
│   │   ├── routers/       # 一个资源一个文件（auth/admin/checkin…）
│   │   ├── services/      # 业务逻辑，router 只做参数校验和编排
│   │   └── utils/         # 图片处理 / 存储 / 地理位置等纯函数
│   ├── alembic/versions/  # 迁移脚本，命名 00N_描述.py
│   ├── migrate.py         # 启动前自动迁移入口（备份→迁移→回填→种子）
│   ├── seed.py            # 幂等种子数据
│   └── tests/             # 按模块划分的回归测试
├── frontend/
│   ├── admin/             # 管理后台（index.html + app.js + admin.css）
│   └── student/           # 用户端（同构）
├── Dockerfile
├── docker-entrypoint.sh
└── scripts/deploy.sh
```

设计规则：
- **router 薄、service 厚**：事务与业务规则全部在 service，router 不直接写 ORM 查询
- **config.py 收口所有环境变量**，每个变量都有本地开发默认值 + Docker 环境变量覆盖
- API 路径规范：用户端 `/api/xxx`，管理端 `/api/admin/xxx`，健康检查 `/api/health`
- 端口分配：宿主机端口用 9 开头的 4-5 位数（9000/9001…），容器内统一 8000

### 阶段3：数据库设计与迁移

**核心纪律：严禁重置数据库。** 一切 schema 变更走增量迁移，且迁移必须防御式编写。

- 新增列一律可空（或带服务端默认值），业务代码对 NULL 做回退处理
- 迁移脚本先检查表/列是否存在再操作（SQLite 无 `IF NOT EXISTS` 列语法，用 inspector）
- `migrate.py` 启动时自动执行：备份 → 三场景迁移（首次部署 create_all+stamp / 有数据无版本记录 stamp / 正常 upgrade head）→ 数据回填 → 幂等种子
- 模板见 [templates/migrate.py.template](templates/migrate.py.template)

### 阶段4：后端实现

- 每个写操作接口：Pydantic 校验 → 权限依赖（`require_role`）→ service 处理 → 统一异常转 HTTPException
- 时间统一用 offset-naive UTC 或统一 aware，**禁止混用**（比较会直接抛异常）
- 分页列表接口支持状态筛选参数；管理端列表 join 用户表返回昵称而非裸 ID
- 涉及积分/库存等数值变更的操作必须落审计字段（operated_by / operated_at / note）

### 阶段5：前端实现

- 静态资源引用**必须相对路径**（`./app.js` 而非 `/app.js`），否则子路径部署（`/homework/`）直接 404
- API base 运行时探测子路径前缀，不硬编码
- 发版时给资源加版本参数 `app.js?v=YYYYMMDD` 强制刷新缓存
- 移动端（≤640px）：表格转卡片、底部 Tab、按钮 ≥44px、输入字号 ≥16px（防 iOS 缩放）
- CDN 用国内镜像源并准备回退（unpkg 直连可能超时）

### 阶段6：安全加固

必做清单（详见 [best-practices.md](best-practices.md)）：

- [ ] 密钥强制环境变量注入，启动时拒绝弱密钥（长度 <32、低熵、常见弱词）
- [ ] 密码 PBKDF2/bcrypt 加盐哈希；密码最小 8 位；用户名仅字母数字
- [ ] JWT 有效期 ≤7 天；`.secret_key` 落盘复用保证重启不失效
- [ ] CORS 白名单收窄到实际来源；方法和请求头也收窄
- [ ] 安全响应头：X-Frame-Options / X-Content-Type-Options / X-XSS-Protection
- [ ] 敏感接口速率限制（登录、改密、上传）
- [ ] 上传校验：魔数校验 + SVG/HTML 伪装检测 + 尺寸上限
- [ ] 生物特征等敏感数据 AES 加密后存储
- [ ] 容器非 root 运行（专用 uid），入口脚本修复数据卷属主后降权
- [ ] `.gitignore` 覆盖 `*.db` / `.secret_key` / `.env` / `uploads/` / `.backups/`

### 阶段7：测试验证

- 回归测试按模块拆文件（`tests/test_auth.py`、`test_checkin.py`…），带 `run_all.py` 一键跑
- 每个功能至少覆盖：正常路径、权限拒绝（403）、重复操作拒绝（400）、边界值
- 部署前后用浏览器做只读冒烟：页面渲染、静态资源 200、关键 API 返回、控制台零报错
- 验证数据一致性：部署前后关键表行数逐项对比

### 阶段8：部署上线

完整流程与脚本模式见 [deployment.md](deployment.md)。核心原则：

1. **部署前必备份**，SQLite WAL 模式下用 `sqlite3.Connection.backup()` 而非裸 `cp`
2. **数据卷永不删除**，容器可随意重建
3. 健康检查用**超时轮询**（迁移可能耗时 20s+），不用固定 sleep
4. 部署脚本任何一步失败必须**中断并如实报错**，禁止 `2>/dev/null; echo OK` 式谎报
5. 部署后验证：镜像 ID 一致性、迁移版本号、行数对比、功能冒烟

## 常见陷阱速查

| 陷阱 | 后果 | 规避 |
|------|------|------|
| 前端绝对路径引资源 | 子路径部署 404 | 一律 `./` 相对路径 |
| 裸 cp 备份 WAL 库 | 丢最近事务 | sqlite3 backup API |
| naive/aware datetime 混用 | 比较直接抛异常 | 全局统一一种 |
| 服务器有 systemd 看门狗 | docker rm 后旧容器复活撞名 | 部署前探测单元，经 systemctl 启停 |
| 重建容器覆盖 CORS 白名单 | 公网入口跨域失败 | 从旧容器 inspect 沿用 Env |
| bind mount 属主 root | 非 root 容器写库 500 | 入口脚本 chown 后降权 |

## 参考文档

- 各环节提示词模板：[prompts.md](prompts.md)
- 最佳实践与踩坑详解：[best-practices.md](best-practices.md)
- 部署流程与脚本模式：[deployment.md](deployment.md)
- 可复用模板：[templates/](templates/) 目录（Dockerfile、compose、入口脚本、migrate.py、config.py、.gitignore）
