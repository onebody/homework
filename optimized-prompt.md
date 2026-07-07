# 兑换记录后台管理系统 — 需求提示词

## 项目概述

基于现有的暑假作业打卡系统（FastAPI + Vue3 前端），开发一套**兑换记录后台管理模块**，供管理员对用户提交的兑换申请进行审核与处理。系统需同时支持 PC 端和移动端浏览器访问。

---

## 一、数据模型

### 兑换记录表 `Redemption`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 主键 |
| user_id | Integer, FK → users.id | 兑换用户 |
| prize_id | Integer, FK → prizes.id | 兑换奖品 |
| prize_name | String(64) | 奖品名称（冗余，防止奖品删除后记录丢失） |
| cost_points | Integer | 消耗积分 |
| status | String(16) | 状态：`pending`（待核实）/ `approved`（已兑现）/ `rejected`（已拒绝） |
| review_note | String(256), 可空 | 审核备注（管理员填写） |
| reviewed_by | Integer, FK → users.id, 可空 | 操作管理员 |
| reviewed_at | DateTime, 可空 | 操作时间 |
| created_at | DateTime | 申请时间 |

---

## 二、后端 API 设计

### 管理员接口（需 JWT 鉴权，角色 = admin）

```
GET    /api/admin/redemptions              # 兑换记录列表（分页 + 状态筛选）
    ?status=pending|approved|rejected      # 可选，按状态过滤
    &page=1&page_size=20                   # 分页参数
    → 返回：{ items: [...], total: int, page: int }

GET    /api/admin/redemptions/{id}         # 兑换记录详情
    → 返回完整记录 + 用户昵称 + 奖品详情

PUT    /api/admin/redemptions/{id}/review  # 核实操作
    Body: { action: "approve" | "reject", note: "备注(可选)" }
    → approve：status → approved，记录 reviewed_by + reviewed_at
    → reject：status → rejected，记录 reviewed_by + reviewed_at
    → 已审核的记录不可重复操作，返回 400
```

### 数据统计

```
GET    /api/admin/stats                    # 仪表盘统计（已有接口扩展）
    → 新增字段：pending_count（待核实数量）、approved_count、rejected_count
```

---

## 三、管理端前端（Admin）

### 3.1 兑换记录列表页

- **顶部统计栏**：待核实 N 条 / 已兑现 N 条 / 已拒绝 N 条，数字用醒目标签展示
- **筛选栏**：状态筛选下拉框（全部 / 待核实 / 已兑现 / 已拒绝）+ 搜索框（按用户名模糊搜索）
- **表格/列表**：

| 列名 | 内容 |
|------|------|
| 用户 | 昵称（username） |
| 兑换内容 | 奖品名称 |
| 消耗积分 | cost_points |
| 申请时间 | created_at，格式 YYYY-MM-DD HH:mm |
| 状态 | 彩色标签：🟡待核实 / 🟢已兑现 / 🔴已拒绝 |
| 操作 | 「核实」按钮（仅 pending 状态显示） |

- 待核实数量 > 0 时，导航栏显示红色角标提示

### 3.2 核实操作弹窗

点击「核实」按钮后弹出模态框：

```
┌──────────────────────────────┐
│  兑换详情核实                  │
├──────────────────────────────┤
│  用户：小明                    │
│  奖品：精美笔记本              │
│  消耗积分：50                  │
│  申请时间：2026-07-07 14:30    │
├──────────────────────────────┤
│  审核备注：[________________]  │
│                              │
│  [ ✅ 确认兑现 ]  [ ❌ 拒绝 ]  │
└──────────────────────────────┘
```

- 操作成功后自动关闭弹窗、刷新列表
- 操作失败显示错误提示

### 3.3 状态标签样式

```css
.badge.pending  { background: #fef3cd; color: #856404; }  /* 黄色 */
.badge.approved { background: #d4edda; color: #155724; }  /* 绿色 */
.badge.rejected { background: #f8d7da; color: #721c24; }  /* 红色 */
```

---

## 四、移动端适配（响应式设计）

### 4.1 断点规则

- `≤ 640px`：移动端布局
- `> 640px`：桌面端布局

### 4.2 移动端具体要求

| 元素 | 移动端适配方案 |
|------|--------------|
| 导航栏 | 底部 Tab 栏或汉堡菜单，兑换记录入口置顶 |
| 统计栏 | 横排 3 个卡片，等宽自适应 |
| 记录列表 | 卡片式布局（非表格），每张卡片展示一条记录 |
| 操作按钮 | 全宽按钮，最小高度 44px（Apple HIG 推荐触控尺寸） |
| 弹窗 | 全屏底部滑入式（bottom sheet），而非居中弹窗 |
| 表单元素 | input / select 最小高度 44px，字号 ≥ 16px（防止 iOS 自动缩放） |
| 间距 | 卡片间距 12px，内边距 16px |

### 4.3 移动端卡片样式示例

```
┌─────────────────────┐
│ 小明          🟡待核实 │
│ 精美笔记本 · 50积分   │
│ 2026-07-07 14:30     │
│ [ 核实处理 ]          │
└─────────────────────┘
```

---

## 五、安全性要求

1. **JWT 鉴权**：所有管理接口需验证 `Authorization: Bearer <token>`
2. **角色校验**：接口层校验 `user.role == "admin"`，非管理员返回 403
3. **防重复操作**：后端校验 `status != "pending"` 时拒绝操作，返回 400
4. **操作日志**：每次审核操作记录 `reviewed_by`、`reviewed_at`、`review_note`
5. **前端守卫**：未登录管理账号时跳转登录页，路由级别拦截

---

## 六、技术栈约束

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy 2.0 + SQLite（WAL 模式） |
| 前端 | Vue 3 CDN 模式（无需构建），原生 fetch API |
| 样式 | 内联 CSS 或独立 CSS 文件，CSS Variables 主题色 |
| 鉴权 | JWT（python-jose），token 存 localStorage |
| 部署 | uvicorn 单进程，端口 8000 |

---

## 七、交付物

1. `backend/app/routers/admin.py` — 新增兑换记录管理相关端点
2. `backend/app/models.py` — Redemption 模型扩展（review_note / reviewed_by / reviewed_at）
3. `frontend/admin/index.html` — 兑换记录管理页面（含列表 + 核实弹窗）
4. `frontend/admin/app.js` — 数据加载、筛选、审核操作方法
5. `frontend/admin/admin.css` — 响应式样式（含移动端断点适配）
