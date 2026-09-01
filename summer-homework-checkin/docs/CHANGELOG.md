# 代码变更记录（CHANGELOG）

> 暑假作业打卡系统（三年级）· 版本历史
> 遵循「新增 / 改进 / 修复」分类，最新版本在前。

---

## v1.7.0（2026-08-30）— 成长农场（farm 模块）

### 新增
- **成长农场游戏模块**：4 张新表（farm_templates / farms / farm_plots / farm_energy_log）+ 1 处可空 ALTER（site_config.farm_default_name），Alembic 016 幂等防御式迁移；既有数据零触碰。
- **能量转化与农场养成**：学习任务审核通过 +10 ⚡、打卡审核通过 +5 ⚡（`approve_submission`/`approve_checkin` 审核联动挂钩，延迟导入避免循环依赖）；开通时历史已审核成果一次性回填（`backfilled` 守卫去重，无农场时钩子静默跳过不丢能量）。
- **养成玩法**：种菜 -20 ⚡（120 分钟成熟，收获 +30）、养殖 -50 ⚡（480 分钟长成，收获 +80）、浇树 -50 ⚡/次；成长树累计 1500 能量育成大树（森林 +1 归零循环），阶段门槛 100/400/900，地块上限 = 4 + 阶段 + 森林数；能量全量流水可查。
- **个性化命名**：学生开通时自定义（≤32 字符）+ 随时改名；管理员可配置站点默认乐园名（置空回退内置默认）。
- **模板选择机制**：内置 3 模板——田园·稻香小镇 / 科幻·星际温室 / 卡通·糖果农庄（`seed.py` 幂等种子），各自独立作物/动物素材与场景风格；可随时切换，管理端可启停（停用后不可新选，已开通农场不受影响）。
- **学生端成长农场视图**：独立 `farm.js`（mixin 注入）+ `farm.css`；底部新增 🌱 tab；开通引导（能量规则 + 模板选择 + 命名）、农场场景（乐园头部/成长树进度/地块网格/成熟高亮）、能量流水分页；三模板主题色 + default/cartoon 双站点主题适配。
- **管理端成长农场子页**：数据概览（农场数/能量汇总/森林总数/Top10 排行）+ 默认乐园名配置 + 模板启停，独立 `farm.js` mixin。
- **测试**：`tests/test_farm.py` 8 组用例（回填去重/能量收支/收获循环/地块上限/森林育成/越权 404/改名校验/模板启停），`pytest tests/` 63 用例全绿；E2E 28 项全过。

### 修复
- `migrate.py` 首部署建表缺陷：`create_all` 前先导入 `app.models` 注册 metadata（此前 metadata 为空，建表实为 seed 兜底完成），并在建表后 `engine.dispose()` 防连接池缓存旧状态。
- `/api/farm/status` 已开通时也返回能量规则 `rules`（前端种植/浇树消耗展示依赖）。

---

## v1.6.0（2026-08-30）— 多学段学习成长计划（learning 模块，后端 API 版本号 1.3.0）

### 新增
- **学习成长计划模块**：9 张新表（subjects / class_groups / semesters / learning_plans / learning_tasks / progress_records / task_submissions / user_badges / learning_config）+ 3 处可空 ALTER（users.class_id、users.study_streak/study_longest_streak、pet_feed_log.trigger_task_submission_id），Alembic 014/015 幂等迁移；暑期打卡数据零触碰。
- **模板→实例化**：`learning_plans` 单表双角色（template/instance），学生实例化后任务独立推进（`template_task_id` 回链），同模板重复实例化幂等返回既有实例；模板按年级/班级隔离，越权构造 403。
- **任务四态**：todo/doing/done 存库，逾期（overdue）由 `computed_status()` 查询时计算绝不写库；进展记录驱动 todo→doing 自动流转。
- **审核联动对齐 `approve_checkin` 范式**：审核通过 → 发积分 → 重算连学天数 → 随机活跃宠物 +XP（`feed_type="task"` 流水）→ 双向通知 → 勋章判定（plan_first/streak7/full_plan 等，幂等）；支持 auto（提交即过）/ parent（家长审核）/ admin（管理员审核）三种模式运行时切换。
- **WebSocket 实时通知**：`/api/ws/notifications?token=` 鉴权建连，30s 心跳剔除死连接，推送失败静默；前端指数退避重连（1/2/4s…30s 上限），连续 3 次失败降级 30s 轮询 `/api/learning/notifications/unread`，通知不丢。
- **学生端计划视图**：独立 `plan.js`（mixin 注入，app.js 仅 +2 行）+ `plan.css`；SVG stroke-dasharray 环形进度、四态任务卡、勋章墙；学期/假期模式默认落地计划视图并展示今日待办，暑期打卡入口任何模式下保留；default/cartoon 双主题 CSS 变量适配。
- **家长端**：孩子计划监督视图（环进度 + 任务列表）与内联审核（仅 `review_mode=parent`，经 `_resolve_child` 校验绑定）。
- **管理端学习计划菜单**：学科/学期/班级（含批量分班）/模板（任务维护、发布、按班级或年级批量指派）/审核队列 6 子页 + 运行模式与审核模式配置；全流程无需改库。
- **预设学科**：`seed.py` 新增 `seed_learning_presets()` 幂等预置 8 学科（按学段下限/上限过滤）。
- **测试**：`tests/test_learning_plan.py` 8 组 30 用例（四态边界/模板隔离/实例化幂等/三模式审核/文件库 10 线程并发恰 1 approved/连学天数/模式切换回归/进展记录），`pytest tests/` 55 用例全绿。

### 安全 / 兼容
- 并发重复发奖双保险：部分唯一索引 `UNIQUE(task_id) WHERE review_status='approved'`（014 迁移）+ `approve_submission` 服务层幂等守卫。
- CSP 同步放宽 `connect-src 'self' ws: wss:`（后端 main.py 与 nginx 两处）；nginx 增加 WebSocket Upgrade/Connection 头与 3600s 超时。
- 全部字段可空新增，`/api/parent/*` 既有签名不变；切回 summer 模式后 checkins/积分/宠物数据逐项不变（回归测试覆盖）。

---

## v1.5.0（2026-08-20）— 宠物乐园·食物适配性校验与生态反馈

### 新增
- **食物适配性校验系统**：4 种饮食类型（carnivore/herbivore/omnivore/special）× 8 种食物分类的完整映射矩阵，5 级适配评价（perfect/suitable/caution/warning/danger）；管理员手动设置优先级最高，支持按物种特化。
- **生态反馈机制**：喂食 warning/caution 食物触发 2 小时生病状态（期间禁止喂养）；连续 3 次 perfect 喂养触发 +20% XP 连击加成（`round()` 修复浮点精度问题）。
- **管理后台适配性矩阵**：33 种宠物 × 12 种食物颜色块矩阵视图（`GET /api/admin/pets/suitability-matrix`），异常喂养记录查询（`GET /api/admin/pets/sick-records`），食物适配等级手动调整（`PUT /api/admin/pets/foods/{id}/suitability`）。
- **前端适配性展示**：食物卡片 5 级 emoji 标识，danger 食物置灰不可点，warning 食物弹确认框，宠物卡片生病横幅 + 饮食标签 + 连击脉冲动画。
- **Alembic 迁移 010→011→012**：宠物系统表 → 食物商店扩展 → 适配性校验字段。
- **上线前安全检测**：52 项测试全部通过，评分 9.2/10（A 优秀），覆盖认证授权/越权防护/输入校验/速率限制/容器安全/业务逻辑。

### 改进
- 33 种宠物种类全量配置饮食类型（seed.py 精确匹配 + 关键词模糊匹配兼容旧数据）。
- 12 种食物配置适配等级与说明（suitability_level/suitability_note）。
- 宠物状态接口增强（`GET /api/pet/status` 返回 diet_type/sick/streak 信息）。
- 食物列表接口增强（`GET /api/pet/foods` 返回每种食物的适配性信息）。

### 安全
- 登录速率限制验证通过（5 次锁定 15 分钟 + 60 秒频率限制）。
- 容器安全加固验证通过（read_only + cap_drop ALL + 端口绑定 127.0.0.1）。
- CORS 白名单生产不含 localhost，伪造 Token 返回 401。

---

## v1.4（2026-08）— 企微智能机器人双向消息

### 新增
- **企微双向机器人**（`GET/POST /api/wecom/callback`）：基于企微「智能机器人」回调协议，群内 @机器人支持与钉钉完全一致的「统计/待审核/查询 <昵称>/通过拒绝 <打卡ID>」指令（复用 `dingtalk_bot_service.handle_command`）；回调报文 AES-256-CBC 加解密 + SHA1 字典序验签（`utils/wecom_crypto`），被动回复采用 stream 类型一次性应答，msgid LRU 排重防网络重试重复执行审核。
- 推送配置新增企微机器人 Token 与 EncodingAESKey 字段（迁移 009），后台「消息推送」页双向消息区块拆为钉钉/企微两子块，展示各自回调地址；EncodingAESKey 保存时校验 43 位长度；「允许群内审核」开关对两渠道共同生效。

### 安全
- 企微回调未配置 Token/密钥时直接 403；签名比对用 `hmac.compare_digest` 防时序侧信道；指令留痕（PushLog）不落 Token/密钥。

---

## v1.3（2026-07）— 消息推送、时区治理与站点动态配置

### 新增
- **Webhook 消息推送模块**：打卡提交/通过/拒绝事件实时推送钉钉/企业微信群机器人；后台「消息推送」配置页（开关/渠道/事件过滤/限频）、测试发送、推送日志列表（`webhook_push_service` + 迁移 002）。
- **钉钉双向机器人**（`POST /api/dingtalk/outgoing`）：群内 @机器人支持「统计/待审核/查询 <昵称>/通过拒绝 <打卡ID>」指令，加签 HMAC-SHA256 验签，群内审核复用后台同一审核逻辑。
- **站点动态配置**：学生端页面标题与登录页欢迎标语后台可配（「⚙️ 系统设置」页），公开 `GET /api/site-config` + 管理端 `GET/PUT /api/admin/site-config`，置空恢复默认值，刷新即生效（`SiteConfig` 表 + 迁移 004）。
- 项目总结文档 [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)。

### 改进
- **全链路时区治理**：存储统一为 naive 北京时间（`utils/timeutil.now_local()` 显式 +8），Dockerfile 增加 `TZ=Asia/Shanghai`；迁移 003 对 11 张表历史时间戳整体 +8h 平移并重算 `check_date`，修复前端时间显示差 8 小时、早 8 点前打卡归属前一天的问题。
- 推送异步化（daemon 线程），异常仅记 PushLog，不影响打卡主流程；Webhook URL 白名单防 SSRF，日志不落 URL。
- 静态资源版本号更新至 `v=20260731`。

### 修复
- `challenge_service` 解锁时间比较统一为 naive 北京时间（`_make_naive`），消除 naive/aware 混比风险与 unlock_at 隐藏 8 小时偏差。

---

## v1.2 / v1.2.1（2026-07）— 安全加固与仓库卫生（补记）

### 安全
- 安全审计发现项修复（v1.2.1）；全库敏感信息清理（数据库/密钥/用户数据不入库）。
- 根 `.gitignore` 门禁体系：密钥/证书/环境变量/数据库/上传照片/备份/日志全类目拦截。
- 双环境增量部署脚本 `scripts/deploy.sh`（部署前自动备份、保留数据卷、健康检查）。

---

## v1.1（2026-07）— 管理后台仪表盘增强

### 新增
- **管理后台数据概览全面增强**：8 个核心指标卡片（总用户/本月活跃/今日打卡/积分发放/待审核/待兑换/最高连续/日均打卡）。
- **可视化图表**（Chart.js 4.4）：近 30 天打卡趋势折线图、用户类型分布饼图、奖品兑换类别柱状图。
- **快捷操作区**：一键跳转待审核打卡/待处理兑换/最新记录，统计数据导出为 TXT。
- **系统状态面板**：服务运行时长、数据库连接状态、有效打卡/绑定关系统计、最新系统通知。
- **后端 `GET /api/admin/dashboard`**：富统计接口，返回多维度统计 + 图表数据 + 系统状态。

### 改进
- 仪表盘响应式网格布局，卡片式设计 + 颜色编码 + 图标，移动端自适应。
- 手动刷新按钮，支持实时重载数据与图表重绘。
- 修复 admin.css 中 `text-nowrap`/`text-ellipsis` 非标准属性为标准 `white-space:nowrap`/`text-overflow:ellipsis`。

---

## v1.0（2026-07）— 学生端菜单重构与文档体系

### 新增
- **底部导航重构为 5 主菜单**：🏠 首页、📝 打卡闯关、🎰 抽奖、🛍️ 商城、👤 我的。
- **「打卡闯关」合并页**：将原「打卡」与「闯关」合并为一个页面，页内子 tab（📸 每日打卡 / 🏆 闯关任务）切换，进入时预加载、切换不重复请求。
- **独立「抽奖」主菜单**（路径 `/lottery`）：从商城中独立出来，实现转盘抽奖 UI —— 抽奖券数量醒目展示、`conic-gradient` 彩色转盘、5 圈精准落点动画（4s 缓动）、中奖结果与抽奖记录。
- **项目文档体系**（`docs/`）：架构设计、功能模块说明、API 接口文档、部署运维指南、用户操作手册、变更记录。

### 改进
- tabbar 改为图标 + 文字纵向堆叠，适配 5 项与「打卡闯关」四字；`env(safe-area-inset-bottom)` 适配全面屏，窄屏（≤360px）字号自适应。
- 转盘与子 tab 样式响应式（`max-width:80vw` + 媒体查询），移动端 / PC 端均良好显示。
- 路由 `go()` 新增 `checkin-challenge` 与 `lottery` 分支，保留家长模式（`/api/parent/*`）与 `BASE_PATH` 子路径拼接逻辑。

### 修复
- 转盘抽奖落点角度计算，确保动画停在与后端结果一致的分区。

---

## v0.9 后修订（2026-07）

### 修复
- **公网访问静态资源 404**：CSS/JS 由绝对路径改为相对路径（`./student.css`、`./app.js`、`./admin.css`），Vue CDN 由 `unpkg.com` 改为国内 `cdn.bootcdn.net`，解决子路径部署下资源加载失败与模板未渲染（显示原始 `{{ }}`）问题。

### 新增 / 改进
- **转盘抽奖改造**：抽奖交互由按钮式改为转盘式。
- **打卡照片上传修复**。
- **前端子路径部署适配**：`BASE_PATH` 自动检测 `/homework` 前缀，`fixUrl` 统一处理上传资源 URL。
- RepoWiki 文档更新同步。

---

## v0.9（2026-07-08）

### 新增
- 密码修改（所有角色通用，旧密码 → 新密码）。
- 家长端解绑孩子（`DELETE /api/parent/unbind/{student_id}`），解绑后可重新绑定。
- 全局回车提交，所有表单支持 Enter 快捷操作。
- 速率限制器（登录 10 次/分钟、注册 5 次/分钟），防暴力破解。

### 改进
- 管理员默认密码通过 `ADMIN_INIT_PASSWORD` 指定，未设置时自动生成随机密码。
- 回归测试全面重构 —— 8 个独立模块、71 个测试用例；支持多环境（本地/生产）运行。

### 修复
- 纯色 JPEG 照片因体积过小被拒绝的问题。
- 测试中的速率限制冲突（可用 `RATE_LIMIT_ENABLED=0` 关闭）。

---

## 早期版本

- **家长绑定学生功能**：家长凭孩子绑定码关联账号，代打卡/查看。
- **家长登录空白页修复** + 综合开发文档。
- **Alembic 数据库迁移集成**：支持增量更新部署。
- **安全加固**：清除全站明文账号密码，改用环境变量与随机生成机制。
- **初始化**：暑假作业打卡系统、积分系统全量代码。

---

## 版本号说明

| 版本 | 主题 |
| --- | --- |
| v1.0 | 学生端菜单重构（打卡闯关合并 + 独立转盘抽奖）+ 文档体系 |
| v0.9 | 密码修改 / 解绑 / 回车提交 / 限流 / 测试重构 |
| 早期 | 打卡核心、家长绑定、防代打卡、安全加固、迁移集成 |
