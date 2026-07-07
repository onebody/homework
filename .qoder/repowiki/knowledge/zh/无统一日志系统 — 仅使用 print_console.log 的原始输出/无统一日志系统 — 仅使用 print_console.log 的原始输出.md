---
kind: logging_system
name: 无统一日志系统 — 仅使用 print/console.log 的原始输出
category: logging_system
scope:
    - '**'
source_files:
    - points-system/backend/app/main.py
    - summer-homework-checkin/backend/app/main.py
    - snake-game/js/main.js
---

本仓库未建立任何统一的日志系统。两个 FastAPI 后端（points-system、summer-homework-checkin）均未导入 Python 标准库 `logging`，也未引入 loguru、structlog、python-json-logger 等第三方日志框架；应用启动入口 `app/main.py` 中没有任何 logger 初始化、中间件或异常处理器来收集结构化日志。业务代码中的诊断信息全部通过 `print()` 直接输出到标准输出，主要集中在 `seed.py` 和 `test_review.py` 这类一次性脚本中，运行时服务代码几乎不使用任何日志调用。

前端贪吃蛇游戏（snake-game）同样没有日志抽象层，所有调试与错误信息均通过浏览器 `console.log` / `console.warn` / `console.error` 直接打印，例如 `js/main.js`、`js/audio/AudioManager.js`、`js/core/GameEngine.js` 等处散落着 console 调用，但无任何集中化的日志收集、分级或持久化机制。

由于缺乏统一的日志框架、级别策略、结构化字段约定以及日志路由/落盘配置，该仓库在当前阶段不具备可观测性的日志能力，后续如需增强应优先考虑在 FastAPI 应用中集成结构化日志中间件并在前端封装统一的日志上报模块。