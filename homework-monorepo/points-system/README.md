# 打卡积分 + 积分兑换奖品 模块

一个**干净、可独立运行**的「打卡赚积分 → 积分兑换奖品」功能模块。技术栈：FastAPI + SQLAlchemy 2.0 + SQLite + 原生 HTML/JS（无构建、无 CDN 依赖）。

> 本模块与 `summer-homework-checkin`（暑假打卡系统）解耦，是该业务逻辑的**通用、最小化实现**，便于移植或作为子模块集成。

---

## 1. 快速开始

```bash
cd points-system/backend
python seed.py                 # 初始化演示数据：2 个用户 + 4 个奖品 + 5 个抽奖奖池
python run.py                  # 启动服务（默认 http://127.0.0.1:8000）
# 打开浏览器访问前端首页（含打卡、积分、积分兑换抽奖券、抽奖、奖品、各类记录）
```

本仓库演示已运行在 **http://127.0.0.1:8011**（避免与既有项目 8000 端口冲突）。

- 学生/用户端首页：`/`
- 后端 API 前缀：`/api`

演示账号：`小明(xiaoming)` 初始 260 分、`小红(xiaohong)` 初始 120 分（已预置积分，可直接体验「积分兑换抽奖券」）。

> 兑换比例：`config.POINTS_PER_TICKET = 50`（每 50 积分换 1 张抽奖券）；每次抽奖固定消耗 1 张券。

---

## 2. 数据库表结构设计

共 10 张表，在「用户 / 积分账户 / 积分流水 / 打卡记录 / 奖品 / 兑换记录」基础上，新增抽奖券体系。

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `users` | `id, username, display_name` | 用户（积分账户归属主体） |
| `point_accounts` | `user_id, balance, total_earned, total_spent, lottery_tickets` | 积分账户，每人一行；`lottery_tickets` 为抽奖券余额（≥1 即解锁抽奖） |
| `point_ledgers` | `user_id, tx_type(earn/spend), amount, balance_after, ref_type, ref_id, note` | 积分流水，每笔收支一条，含变动后余额，用于对账 |
| `checkins` | `user_id, check_date, points_earned, streak, bonus` | 打卡记录，每日一行；`streak` 记录连续天数 |
| `prizes` | `name, cost_points, stock, valid_from, valid_to` | 奖品：所需积分、库存、兑换有效期 |
| `redemptions` | `user_id, prize_id, cost_points, status` | 兑换记录：每次成功兑换一条 |
| `conversions` | `user_id, qty, cost_points, status` | 积分兑换抽奖券记录：每次成功兑换一条 |
| `lottery_ticket_ledgers` | `user_id, tx_type(issue/consume), amount, balance_after, ref_type, ref_id, note` | 抽奖券流水，发放/消耗各一条，含变动后余额 |
| `lottery_prizes` | `name, weight, stock, is_win, sort_order` | 抽奖奖池，按 `weight` 加权随机；`stock=None` 表示不限量 |
| `lottery_draws` | `user_id, prize_id, prize_name, is_win` | 抽奖记录：每次成功抽奖一条 |

**关键设计**：抽奖权限**不单独存储状态位**，而是由 `point_accounts.lottery_tickets >= 1` 派生。这样从根上避免「券没发但抽奖已解锁」「券发了权限没开」这类状态与余额不一致。

**防重复设计**：`checkins` 表对 `(user_id, check_date)` 建立**唯一约束**，从数据库层兜底「每日仅可打卡一次」。

---

## 3. 后端 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/checkin` | 打卡（body: `user_id`）。每日一次，得固定积分，连续 7 天额外奖励 |
| GET  | `/api/points?user_id=` | 查询积分账户（余额/累计收入/支出） |
| GET  | `/api/ledger?user_id=&limit=` | 查询积分流水 |
| GET  | `/api/prizes?user_id=` | 奖品列表（传 `user_id` 时返回 `can_redeem` 标记） |
| POST | `/api/redeem` | 兑换奖品（body: `user_id, prize_id`），扣积分+扣库存+生成记录 |
| GET  | `/api/redemptions?user_id=` | 查询兑换记录 |
| POST | `/api/convert` | **积分兑换抽奖券**（body: `user_id, qty`），扣积分+发券+双流水 |
| GET  | `/api/conversions?user_id=` | 查询积分兑换抽奖券记录 |
| GET  | `/api/ticket-ledger?user_id=` | 查询抽奖券流水（发放/消耗） |
| GET  | `/api/lottery/pool` | 抽奖奖池配置（权重、库存、是否中奖） |
| POST | `/api/lottery/draw` | **发起抽奖**（body: `user_id`），校验券≥1→扣券→加权随机抽奖 |
| GET  | `/api/lottery/draws?user_id=` | 查询抽奖记录 |
| POST | `/api/register` | 注册用户（同时开通积分账户） |
| GET  | `/api/users` | 用户列表（前端切换用） |
| GET  | `/api/dashboard?user_id=` | 一次性返回看板所需全部数据（含 `lottery_tickets` / `can_lottery`） |

---

## 4. 核心业务逻辑

### 4.1 打卡获取积分
- 每日一次，固定 `+POINTS_PER_CHECKIN`（默认 10 分）。
- **连续奖励**：当连续打卡天数 `streak % 7 == 0` 时，额外 `+POINTS_STREAK_BONUS`（默认 20 分）。
- 连续天数计算：以「昨天是否也打卡」判定延续或重置（断签则归 1）。
- 记录：写入 `checkins`（含 `streak`/`bonus`），账户 `balance`、`total_earned` 增加，并写一条 `earn` 流水。

### 4.2 积分兑换奖品
- 校验顺序：`奖品存在` → `在兑换有效期内` → `库存 > 0` → `账户余额 ≥ 所需积分`。
- 任一项不满足即返回明确错误（400/409），**不扣减任何数据**。
- 通过校验后，在**同一事务**内：账户余额与累计支出扣减、奖品库存扣减、生成 `redemptions` 记录、写一条 `spend` 流水。

### 4.3 积分流水与账户管理
- 每笔收入/支出都落 `point_ledgers`，`balance_after` 保存变动后余额，天然形成可对账的流水账。
- 账户 `total_earned` / `total_spent` 与流水双向印证。

### 4.4 积分兑换抽奖券 + 动态解锁抽奖（新增）

**积分转抽奖券（`/api/convert`）**
- 固定比例：`qty` 张抽奖券消耗 `qty * POINTS_PER_TICKET` 积分（默认 50 分/张）。
- 支持单笔或多笔：每次请求传入 `qty`，多次调用累加；余额实时扣减、抽奖券实时增加。
- 余额校验（含最低门槛）：若 `余额 < POINTS_PER_TICKET`（连 1 张都换不起）或 `余额 < 本次所需`，返回 `400` 并提示具体缺口，**不发放任何券**。
- 通过校验后，在**同一事务**内：积分余额扣减、抽奖券增加，并各写一条流水（积分 `spend` + 券 `issue`）。

**抽奖权限动态解锁**
- 解锁条件：`point_accounts.lottery_tickets >= 1` → 前端展示抽奖入口可用。
- 锁定条件：抽奖券消耗至 0 → 入口自动置灰，提示「获取抽奖券即可参与抽奖」。
- 权限由**余额派生**，不存独立状态位，杜绝「券与权限不一致」。

**抽奖扣券与抽奖（`/api/lottery/draw`）**
- 发起前校验抽奖券 ≥ 1（不足直接 `409` 拦截，等价于未解锁）。
- 通过后在**同一事务**内：扣减 1 张券、按 `weight` 加权随机选出奖池奖品（库存有限者同步扣库存）、写抽奖券 `consume` 流水与 `lottery_draws` 记录。
- 券减到 0 时抽奖权限随之自动失效。

---

## 5. 数据一致性（事务处理）

积分扣减与库存扣减的原子性是本模块的核心。实现方式：

1. 所有「读-改-写」操作在同一个 SQLAlchemy `Session` 内完成。
2. 业务校验在**扣减之前**完成；全部通过后才执行写操作。
3. 统一 `db.commit()` 提交；发生异常统一 `db.rollback()`，**余额与库存要么同时成功、要么同时不生效**，不存在半更新。
4. 打卡防重复：`(user_id, check_date)` 唯一约束 + 业务层先查，并发场景由数据库唯一约束兜底（捕获 `IntegrityError` 转 409）。

### 并发与数据一致性（含高并发积分/抽奖券一致性）
- **演示（SQLite）**：在单事务原子性 + 唯一约束基础上，于写路径（`do_convert` / `do_draw`）加**进程内 `threading.Lock`**，把「读-改-写」整体串行化，彻底杜绝 SQLite 下「丢失更新」（两个并发请求读到同一余额、各自扣减、后者覆盖前者）。同时开启 WAL 与 `busy_timeout` 提升并发稳健性。
  - 实测：40 路并发兑换 + 60 路并发抽奖下，积分余额 = 基线 − 流水支出合计、抽奖券余额 = 发放合计 − 消耗合计，且账户余额与最新流水 `balance_after` 完全对账，无负余额 / 负券。
- **生产（PostgreSQL，推荐）**：将进程内锁替换为数据库悲观锁，在 `do_convert` / `do_draw` / `do_redeem` 中对账户行加锁：

  ```python
  acc = db.query(models.PointAccount).filter(...).with_for_update().first()
  ```

  即可在多实例、多写并发下彻底杜绝「超兑 / 负积分 / 券少发」。

---

## 6. 目录结构

```
points-system/
├── backend/
│   ├── app/
│   │   ├── database.py            # 引擎/会话/Base
│   │   ├── config.py              # 积分规则常量
│   │   ├── models.py             # 10 张表 ORM 定义
│   │   ├── schemas.py            # Pydantic 出入参
│   │   ├── services/
│   │   │   ├── points_service.py   # 事务化业务逻辑（打卡/兑换奖品）
│   │   │   └── lottery_service.py  # 事务化业务逻辑（积分转券/抽奖，含并发锁）
│   │   └── routers/
│   │       ├── checkin.py  points.py  prize.py  redeem.py
│   │       ├── convert.py  lottery.py  users.py
│   │   └── main.py               # 应用入口 + 静态托管
│   ├── seed.py                   # 演示数据
│   └── run.py                    # 启动入口
└── frontend/
    ├── index.html  styles.css  app.js   # 原生实现，无 CDN 依赖
```

---

## 7. 验证

端到端测试覆盖（共 **53 项断言全部通过**：积分/兑换 24 项 + 抽奖/兑换抽奖券 29 项）：

**积分兑换抽奖券与抽奖（29 项）**
- 积分不足兑换拦截（0 分换 1 张 / 多张超出余额，均 400）；
- 兑换成功并自动解锁抽奖（券+1、`can_lottery=true`）；
- 抽奖扣券、抽奖记录正确；券耗尽后抽奖自动锁定（409，前端按钮置灰）；
- 积分流水与抽奖券流水对账：末笔流水 `balance_after` = 当前余额/券数；
- **高并发**（40 路兑换 + 60 路抽奖）：积分余额 = 基线 − 支出合计、抽奖券 = 发放 − 消耗，无负余额/负券，权限与余额一致。

**积分与兑换（24 项）**
- 连续第 7 天打卡得 30 分（10 + 20 奖励）、连续天数正确；
- 同日重复打卡被拒（409）；
- 积分不足（400）、库存不足（409）被正确拦截；
- 正常兑换后余额与库存同步扣减、兑换记录与流水一致；
- 账户累计收入/支出与流水对账平衡。
