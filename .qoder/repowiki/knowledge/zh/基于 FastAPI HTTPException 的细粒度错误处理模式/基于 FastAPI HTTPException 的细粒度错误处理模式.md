---
kind: error_handling
name: 基于 FastAPI HTTPException 的细粒度错误处理模式
category: error_handling
scope:
    - '**'
source_files:
    - summer-homework-checkin/backend/app/deps.py
    - summer-homework-checkin/backend/app/services/checkin_service.py
    - summer-homework-checkin/backend/app/services/redeem_service.py
    - summer-homework-checkin/backend/app/services/lottery_service.py
    - points-system/backend/app/services/points_service.py
    - points-system/backend/app/services/lottery_service.py
    - snake-game/js/audio/AudioManager.js
    - snake-game/js/core/GameEngine.js
    - snake-game/js/data/StorageManager.js
---

本仓库包含两个独立的 Python 后端（points-system、summer-homework-checkin）和一个纯前端贪吃蛇游戏，错误处理方式按模块差异明显：

## 1. 后端统一使用 FastAPI HTTPException

两个后端均未定义自定义异常类或全局异常处理器，而是直接在路由层与服务层抛出 fastapi.HTTPException，通过 status_code + detail 字段表达错误语义。

- 认证与鉴权集中在依赖注入中：summer-homework-checkin/backend/app/deps.py 在 get_current_user 中针对未提供令牌、令牌无效/过期、用户不存在、无权限分别返回 401/403。
- 业务校验下沉到 service 层：如 checkin_service.py 对补卡日期格式、范围、重复打卡、人脸校验失败等场景抛出 400；redeem_service.py 对奖品状态、库存、兑换记录状态检查返回 400/404/409。
- 资源缺失统一用 404，冲突用 409，外部服务不可用用 503（如人脸识别服务）。

示例：service 层抛错
raise HTTPException(status_code=400, detail="补卡只能补过去的日期")
raise HTTPException(status_code=409, detail="今日已打卡，请勿重复操作")
raise HTTPException(status_code=503, detail="人脸识别服务暂不可用，请稍后重试")

## 2. 无全局异常中间件 / 自定义响应格式

- points-system/backend/app/main.py 仅注册路由与静态文件挂载，未添加任何异常中间件。
- summer-homework-checkin/backend/app/main.py 仅启用 CORS 中间件与健康端点，同样未覆盖默认异常响应格式。
- 因此所有错误均以 FastAPI 默认的 {"detail": "..."} JSON 结构返回，未做统一包装。

## 3. 前端错误处理（贪吃蛇）

前端采用分散式 try/catch + console.error 策略，无统一错误上报或用户提示机制：

- AudioManager.js 捕获音频播放异常并打印日志
- GameEngine.js 捕获设置加载失败
- StorageManager.js 捕获本地存储读写异常
- EventBus.js 在事件分发时 catch 监听器异常

这些错误不会向用户展示，也不会中断主循环。

## 4. 约定与问题

| 维度 | 现状 |
|------|------|
| 错误类型 | 全部使用内置 HTTPException，无领域异常类 |
| 错误码 | 散落在各文件中，未集中枚举，存在重复字符串 |
| 全局处理 | 无自定义异常处理器，依赖 FastAPI 默认行为 |
| 日志 | 后端未集成结构化日志框架，仅前端有 console.error |
| 可观测性 | 无错误追踪（Sentry 等）或指标收集 |

建议后续引入统一的异常基类、全局异常中间件将错误响应标准化为 {code, message, data} 结构，并在关键路径补充结构化日志。