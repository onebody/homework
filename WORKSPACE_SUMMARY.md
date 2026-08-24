# 工作区快速参考（hanghang_WS）

> 更新时间：2026-08-24 · 版本 v1.6.0 · [GitHub](https://github.com/onebody/homework)

## 项目一览

| 项目 | 状态 | 入口 |
| --- | --- | --- |
| 暑假作业打卡系统 | ✅ 双环境运行 | 本地 `:8003` / 生产 `192.168.8.155/homework/` |
| 积分兑换系统 | ✅ 本地运行 | 本地 `:8001` |
| 2048 游戏 | ✅ 即开即玩 | `2048/src/index.html` |
| 贪吃蛇游戏 | ✅ 本地可玩 | `snake-game/index.html` |

## 最新版本 v1.6.0（2026-08-22）

**宠物乐园 · 多宠物领养 + 改名 + 种类 Emoji 修复**

- 单用户最多领养 3 只宠物（MAX_PETS_PER_USER=3）
- 宠物改名功能（`POST /api/pet/rename`）
- 种类专属 Emoji 显示（修复硬编码默认值问题）
- Hero 卡片 / Mini 列表 / 管理列表数据一致性修复
- `canAdoptMore` 计算属性修复（Vue 3 Options API）

### v1.5.0 回顾（2026-08-20）

- 33 种宠物 × 12 种食物适配矩阵
- 4 种饮食类型（食肉/食草/杂食/特殊）
- 5 级适配评价（perfect/suitable/caution/warning/danger）
- 生病机制（2 小时恢复）+ 连击加成（+20% XP）
- 安全检测评分 9.2/10（A 优秀），52 项测试全通过

## 快速命令

```bash
# 本地部署
bash scripts/deploy.sh local

# 生产部署（密钥认证）
DEPLOY_SSH_HOST=192.168.8.155 DEPLOY_SSH_KEY=~/.ssh/id_ed25519 bash scripts/deploy.sh prod

# 健康检查
curl http://127.0.0.1:8003/api/health
curl http://192.168.8.155:9000/api/health

# 测试账号
# 学生: teststu01/test1234（本地）| 小杭杭/hanghang@123（生产）
# 管理员: admin/（环境变量 ADMIN_INIT_PASSWORD 或 seed 自动生成）
```

## 技术栈

FastAPI 0.115.0 · SQLAlchemy 2.0.35 · Vue 3.5.41 · SQLite WAL · Docker · Nginx · Alembic（12 迁移）

## 文档索引

| 文档 | 路径 |
| --- | --- |
| 阶段性总结报告 | `summer-homework-checkin/docs/PROJECT_STAGE_SUMMARY_20260820.md` |
| 上线前测试报告 | `summer-homework-checkin/docs/PRE_LAUNCH_TEST_REPORT.md` |
| 安全整改报告 | `summer-homework-checkin/docs/SECURITY_REMEDIATION_REPORT.md` |
| 项目总结 | `summer-homework-checkin/docs/PROJECT_SUMMARY.md` |
| 变更记录 | `summer-homework-checkin/docs/CHANGELOG.md` |
| 架构设计 | `summer-homework-checkin/docs/ARCHITECTURE.md` |
| 功能模块 | `summer-homework-checkin/docs/FEATURES.md` |
| API 接口 | `summer-homework-checkin/docs/API.md` |
| 部署运维 | `summer-homework-checkin/docs/DEPLOYMENT.md` |

## 代码统计

- 后端 Python：6,563 行
- 前端 JS：2,708 行
- 前端 CSS：1,030 行
- 文档：17 份 Markdown
