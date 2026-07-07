---
kind: configuration_system
name: 后端硬编码加环境变量覆盖、前端 localStorage 的轻量配置体系
category: configuration_system
scope:
    - '**'
source_files:
    - summer-homework-checkin/backend/app/config.py
    - summer-homework-checkin/backend/run.py
    - summer-homework-checkin/backend/requirements.txt
    - points-system/backend/app/config.py
    - points-system/backend/run.py
    - snake-game/js/core/GameEngine.js
    - snake-game/js/data/StorageManager.js
---

本仓库包含三个独立子模块，每个模块采用不同的配置策略，整体呈现无统一配置框架、以 Python 常量加环境变量为主的轻量风格。

## 1. 暑假作业打卡系统（summer-homework-checkin/backend）
- 核心文件：backend/app/config.py
- 加载方式：纯 Python 模块级常量，通过 os.environ.get(key, default) 读取环境变量；未找到 .env 文件或 python-dotenv / pydantic-settings 等第三方库。
- 可覆盖项：SUMMER_SECRET、GEO_THRESHOLD_METERS、MAX_MAKEUP_PER_MONTH、CHECKIN_POINTS、MAKEUP_POINTS、FACE_MATCH_THRESHOLD、FACE_MODE_ON_ENROLLED 等。
- 默认值策略：所有敏感/环境相关参数均提供合理默认值（如开发密钥、地理阈值 1500m、人脸阈值 0.4），保证本地直接运行无需额外配置。
- 启动入口：run.py 使用 uvicorn 直接 app.main:app，不经过任何配置中间件。
- 依赖约束：requirements.txt 中不含 dotenv/pydantic-settings，确认未引入外部配置库。

## 2. 积分与打卡子系统（points-system/backend）
- 核心文件：backend/app/config.py
- 加载方式：全部为模块级 Python 常量（POINTS_PER_CHECKIN、POINTS_STREAK_BONUS、POINTS_PER_TICKET 等），注释说明生产环境可用环境变量覆盖，但代码中并未实现 os.environ.get 读取逻辑，属于预留但未落地。
- 数据库：SQLite 路径硬编码在 database.py，无配置文件。
- 启动入口：同打卡系统，uvicorn 直启。

## 3. 贪吃蛇游戏前端（snake-game）
- 存储位置：浏览器 localStorage，键名由全局常量 STORAGE_KEY 决定。
- 加载流程：GameEngine.loadSettings() 从 localStorage 读取 JSON，合并 DEFAULT_SETTINGS；StorageManager 提供 getSettings/saveSettings 封装。
- 内容结构：settings 对象与 highScores、achievements、statistics 等数据共用同一 storage key，按字段区分。
- 持久化策略：每次设置变更调用 saveSettings() 写回；最高分、成就、统计均有独立的读写方法。

## 架构与约定
- 配置来源优先级：运行时环境变量大于代码默认值（Python 侧）；用户界面设置大于内置默认值（前端）
- 敏感信息：仅打卡系统通过 SUMMER_SECRET 注入，其余均为业务阈值
- 配置格式：无 YAML/TOML/JSON 配置文件，全部为 Python 常量或 JS 对象
- 多环境支持：仅通过环境变量切换，无 .env 模板或 pydantic Settings 模型
- 前端配置：无服务端下发配置，全部客户端持久化

## 开发者应遵循的规则
1. 新增后端配置项：在对应 app/config.py 中以 os.environ.get("KEY", default) 形式声明，保持默认值可本地运行。
2. 不要引入新的配置库：当前依赖清单极简，避免引入 python-dotenv / pydantic-settings 以保持零依赖部署。
3. 前端新设置：在 StorageManager 中新增 getter/setter，并在 GameEngine.DEFAULT_SETTINGS 中补充默认值。
4. 敏感配置一律走环境变量：禁止将密钥、阈值硬编码到提交代码中。