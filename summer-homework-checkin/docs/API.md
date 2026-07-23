# API 接口文档

> 暑假作业打卡系统（三年级）· HTTP API 参考
> 版本：v1.0 ｜ Base URL：`http://<host>[/homework]`
> 子路径部署时前端自动为所有请求加 `BASE_PATH` 前缀，后端路由本身不含该前缀。

---

## 通用约定

- **认证**：除注册/登录/健康检查外，均需请求头 `Authorization: Bearer <token>`。
- **Token**：登录/注册返回 `access_token`（HMAC 签名），有效期 30 天。
- **内容类型**：JSON 接口用 `application/json`；含文件上传用 `multipart/form-data`。
- **错误响应**：`{ "detail": "错误说明" }`，HTTP 状态码语义化（400/401/403/404/429）。
- **限流**：登录 10 次/分钟、注册 5 次/分钟，超限返回 429（可用 `RATE_LIMIT_ENABLED=0` 关闭）。
- **在线文档**：FastAPI 自带 `GET /docs`（Swagger）与 `GET /openapi.json`。

---

## 1. 认证 `/api/auth`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | 否 | 注册（body: username, nickname, password, role=student\|parent），返回 token + user |
| POST | `/api/auth/login` | 否 | 登录（body: username, password），返回 token + user |
| GET | `/api/auth/me` | 是 | 当前登录用户信息 |
| PUT | `/api/auth/password` | 是 | 修改密码（body: old_password, new_password） |

**登录响应示例**
```json
{
  "access_token": "eyJ1aWQiOjEs...",
  "user": { "id": 1, "username": "admin", "role": "admin", "nickname": "管理员" }
}
```

---

## 2. 打卡 `/api/checkin`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/checkin` | 学生 | 提交打卡（multipart: photo, [proof], [location_lat], [location_lng], check_type=normal\|makeup, [makeup_for_date], [makeup_reason]） |
| POST | `/api/checkin/upload` | 学生 | 通用图片上传 |
| GET | `/api/checkin/today` | 学生 | 今日打卡状态（已打卡/待审核/可补卡次数） |
| GET | `/api/checkin/streak` | 学生 | 连续天数、最长、累计、抽奖券、积分 |
| GET | `/api/checkin/history` | 学生 | 打卡历史列表 |

---

## 3. 抽奖 `/api/lottery`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/lottery/tickets` | 学生 | 当前可用抽奖券数量 |
| POST | `/api/lottery/draw` | 学生 | 抽奖，消耗 1 张券，加权随机 |

**抽奖响应示例**
```json
{
  "is_win": true,
  "prize_name": "彩色铅笔套装",
  "prize_id": 3,
  "tickets_left": 2,
  "message": "恭喜抽中【彩色铅笔套装】"
}
```

---

## 4. 奖品 `/api`（含管理端）

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/prizes` | 是 | 奖品列表（学生可见） |
| GET | `/api/admin/prizes` | 管理员 | 奖品列表（管理视图） |
| POST | `/api/admin/prizes` | 管理员 | 新增奖品 |
| PUT | `/api/admin/prizes/{pid}` | 管理员 | 编辑奖品（概率/库存/上下架/抽奖券配置） |
| DELETE | `/api/admin/prizes/{pid}` | 管理员 | 删除奖品 |

---

## 5. 积分商城 `/api`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/mall` | 学生 | 商城数据（积分、抽奖券、奖品、兑换记录、抽奖记录） |
| POST | `/api/redeem` | 学生 | 积分兑换（body: prize_id） |
| POST | `/api/redeem/{rid}/replace` | 学生 | 替换已兑换奖品（body: new_prize_id） |

---

## 6. 家长 `/api/parent`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/parent/bind` | 家长 | 绑定孩子（body: child_username, bind_code） |
| DELETE | `/api/parent/unbind/{student_id}` | 家长 | 解绑孩子 |
| GET | `/api/parent/children` | 家长 | 已绑定孩子列表 |
| GET | `/api/parent/child-streak/{child_id}` | 家长 | 孩子连续天数/积分/今日状态 |
| POST | `/api/parent/checkin` | 家长 | 代孩子打卡（multipart + child_id） |
| GET | `/api/parent/mall/{child_id}` | 家长 | 孩子商城数据 |
| POST | `/api/parent/redeem?child_id=` | 家长 | 代孩子兑换 |
| POST | `/api/parent/redeem/{rid}/replace` | 家长 | 代孩子替换兑换 |
| GET | `/api/parent/lottery/{child_id}` | 家长 | 孩子抽奖券信息 |
| POST | `/api/parent/lottery/{child_id}/draw` | 家长 | 代孩子抽奖 |
| GET | `/api/parent/notifications` | 家长 | 通知列表 |
| PATCH | `/api/parent/notifications/{nid}/read` | 家长 | 标记通知已读 |
| GET | `/api/parent/child-report/{child_id}` | 家长 | 孩子报告（JSON） |
| GET | `/api/parent/child-report/{child_id}/html` | 家长 | 孩子报告（HTML 可视化） |

---

## 7. 后台管理 `/api/admin`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/admin/dashboard` | 管理员 | 富统计仪表盘（指标卡片 + 图表数据 + 系统状态） |
| GET | `/api/admin/stats` | 管理员 | 基础概览统计（兼容旧接口） |
| GET | `/api/admin/users` | 管理员 | 用户列表 |
| GET | `/api/admin/checkins` | 管理员 | 打卡列表（含异常标记） |
| GET | `/api/admin/checkins/pending-count` | 管理员 | 待审核打卡数 |
| PUT | `/api/admin/checkins/{checkin_id}/review` | 管理员 | 审核打卡（body: review_status, [review_note]） |
| GET | `/api/admin/redemptions` | 管理员 | 兑换记录列表 |
| GET | `/api/admin/redemptions/{redemption_id}` | 管理员 | 兑换记录详情 |
| PUT | `/api/admin/redemptions/{redemption_id}/review` | 管理员 | 审核兑换 |

---

## 8. 闯关任务 `/api/challenge`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/challenge/tasks` | 学生 | 任务列表（含个人状态） |
| GET | `/api/challenge/tasks/{task_id}` | 学生 | 任务详情 |
| POST | `/api/challenge/tasks/{task_id}/checkin` | 学生 | 提交闯关打卡 |
| POST | `/api/challenge/tasks/{task_id}/checkin-with-content` | 学生 | 提交闯关打卡（含文字+附件） |
| POST | `/api/challenge/upload` | 学生 | 闯关附件上传 |
| GET | `/api/challenge/my-checkins` | 学生 | 我的闯关打卡记录 |
| GET | `/api/challenge/admin/tasks` | 管理员 | 任务管理列表 |
| POST | `/api/challenge/admin/tasks` | 管理员 | 新建任务 |
| PUT | `/api/challenge/admin/tasks/{task_id}` | 管理员 | 编辑任务 |
| DELETE | `/api/challenge/admin/tasks/{task_id}` | 管理员 | 删除任务 |
| POST | `/api/challenge/admin/tasks/{task_id}/unlock` | 管理员 | 手动开放任务 |
| GET | `/api/challenge/admin/checkins` | 管理员 | 闯关打卡列表 |
| GET | `/api/challenge/admin/checkins/pending-count` | 管理员 | 待审核闯关打卡数 |
| PUT | `/api/challenge/admin/checkins/{checkin_id}/review` | 管理员 | 审核闯关打卡 |

---

## 9. 报表 `/api/report`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/report/me` | 学生 | 学习报告（JSON） |
| GET | `/api/report/me/html` | 学生 | 学习报告（HTML，可打印下载） |

---

## 10. 人脸 `/api/face`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/face/enroll` | 学生 | 采集人脸底图（multipart: photo） |
| GET | `/api/face/status` | 学生 | 是否已采集 + 底图 URL |
| DELETE | `/api/face/enroll` | 学生 | 撤销人脸底图 |

---

## 11. 系统

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/health` | 否 | 健康检查，返回 `{"status":"ok"}` |
| GET | `/docs` | 否 | Swagger UI |
| GET | `/openapi.json` | 否 | OpenAPI 规范 |

> **提示**：`points-system`（端口 8001）为独立系统，其奖品接口为 `/api/prizes`（非 `/api/products`），健康检查同为 `/api/health`。
