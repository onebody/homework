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
| GET | `/api/parent/learning/plans/{child_id}` | 家长 | 孩子学习计划与任务列表（四态 + 进度汇总） |
| GET | `/api/parent/learning/summary/{child_id}` | 家长 | 孩子学习概览（连学天数/环进度/勋章数） |
| GET | `/api/parent/learning/submissions/pending` | 家长 | 孩子待审核提交（仅 `review_mode=parent` 时可用） |
| PUT | `/api/parent/learning/submissions/{sid}/review` | 家长 | 家长审核（通过/驳回，通过触发积分+宠物XP联动） |

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
| GET | `/api/admin/site-config` | 管理员 | 读取站点配置（学生端标题/欢迎标语原始值，未设置为 null） |
| PUT | `/api/admin/site-config` | 管理员 | 保存站点配置（body: student_title ≤64 字, student_slogan ≤128 字；置空恢复默认） |
| GET | `/api/admin/push-config` | 管理员 | 读取消息推送配置 |
| PUT | `/api/admin/push-config` | 管理员 | 保存推送配置（开关/渠道/Webhook URL 白名单校验/事件过滤/限频） |
| POST | `/api/admin/push-config/test` | 管理员 | 发送测试消息到当前配置的群机器人 |
| GET | `/api/admin/push-logs` | 管理员 | 推送日志列表（不含 Webhook URL，已脱敏） |
| GET | `/api/admin/learning/config` | 管理员 | 学习计划全局配置（运行模式/审核模式/当前学期） |
| PUT | `/api/admin/learning/config` | 管理员 | 切换运行模式（summer/semester/holiday）与审核模式（auto/parent/admin） |
| GET/POST | `/api/admin/learning/subjects` | 管理员 | 学科列表 / 新建学科 |
| PUT/DELETE | `/api/admin/learning/subjects/{sid}` | 管理员 | 编辑 / 删除学科（预设学科禁删） |
| GET/POST | `/api/admin/learning/semesters` | 管理员 | 学期（含寒假/暑假周期）列表 / 新建 |
| PUT/DELETE | `/api/admin/learning/semesters/{sid}` | 管理员 | 编辑 / 删除学期 |
| GET/POST | `/api/admin/learning/classes` | 管理员 | 班级列表（含成员数）/ 新建班级 |
| PUT/DELETE | `/api/admin/learning/classes/{cid}` | 管理员 | 编辑 / 删除班级 |
| POST | `/api/admin/learning/classes/{cid}/members` | 管理员 | 批量分班（body: student_ids[]） |
| GET | `/api/admin/learning/students` | 管理员 | 学生列表（分班选择器用，含班级归属） |
| GET/POST | `/api/admin/learning/templates` | 管理员 | 计划模板列表 / 新建模板 |
| GET/PUT/DELETE | `/api/admin/learning/templates/{tid}` | 管理员 | 模板详情（含任务）/ 编辑 / 删除 |
| POST | `/api/admin/learning/templates/{tid}/tasks` | 管理员 | 模板新增任务 |
| PUT/DELETE | `/api/admin/learning/tasks/{task_id}` | 管理员 | 编辑 / 删除模板任务 |
| POST | `/api/admin/learning/templates/{tid}/publish` | 管理员 | 发布模板（学生端可见） |
| POST | `/api/admin/learning/templates/{tid}/assign` | 管理员 | 批量指派实例化（按 class_id 或 grade，幂等跳过已有实例） |
| GET | `/api/admin/learning/submissions` | 管理员 | 提交审核队列（状态筛选 + 分页） |
| PUT | `/api/admin/learning/submissions/{sid}/review` | 管理员 | 审核提交（通过触发奖励联动，部分唯一索引防重复发奖） |
| GET | `/api/admin/farm/overview` | 管理员 | 成长农场概览（农场数/能量汇总/森林总数/Top10 排行） |
| GET/PUT | `/api/admin/farm/config` | 管理员 | 站点默认乐园名（置空回退内置默认） |
| GET | `/api/admin/farm/templates` | 管理员 | 农场模板列表（含使用中农场数） |
| PUT | `/api/admin/farm/templates/{tpl_id}` | 管理员 | 模板启停（停用后不可新选，已开通农场不受影响） |

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

## 11. 站点配置与钉钉机器人

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/site-config` | 否 | 公开读取学生端标题/欢迎标语（未配置时返回服务端默认值，登录前可用） |
| POST | `/api/dingtalk/outgoing` | 钉钉验签 | 钉钉机器人 Outgoing 回调；加签 HMAC-SHA256 验证（兼容 Token 明文），支持「统计/待审核/查询 <昵称>/通过拒绝 <打卡ID>」指令 |

---

## 12. 系统

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/health` | 否 | 健康检查，返回 `{"status":"ok"}` |
| GET | `/docs` | 否 | Swagger UI |
| GET | `/openapi.json` | 否 | OpenAPI 规范 |
| WS | `/api/ws/notifications?token=` | `?token=` JWT | 实时通知推送（心跳 30s ping；凭证无效关闭 4401；断线前端降级轮询） |

---

## 13. 学习成长计划 `/api/learning`（学生端）

> 模板按年级/班级隔离；任务四态（todo/doing/done 存库，overdue 查询时计算）；
> 审核通过后联动发积分 + 随机活跃宠物 XP（feed_type=task）+ 双向通知 + 勋章。
> 审核模式由管理端 `review_mode` 决定：auto（提交即过）/ parent（家长审核）/ admin（管理员审核）。

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/learning/config` | 学生 | 运行模式/审核模式/当前学期/我的班级 |
| GET | `/api/learning/subjects` | 学生 | 启用中学科（按年级学段过滤） |
| GET | `/api/learning/templates` | 学生 | 可见模板（已发布 + 年级/班级匹配） |
| POST | `/api/learning/plans/instantiate` | 学生 | 实例化模板为个人计划（幂等：已有实例返回既有） |
| GET | `/api/learning/plans` | 学生 | 我的计划列表（含进度汇总） |
| GET | `/api/learning/plans/{plan_id}` | 学生 | 计划详情（任务四态 + 进展/提交记录，校验归属） |
| GET | `/api/learning/summary` | 学生 | 首页卡片（连学天数/环进度/勋章数） |
| GET | `/api/learning/badges` | 学生 | 勋章墙（已解锁 + 未解锁灰态） |
| POST | `/api/learning/tasks/{task_id}/progress` | 学生 | 记录进展（todo→doing 自动流转，percent 钳制 0-100） |
| POST | `/api/learning/tasks/{task_id}/submit` | 学生 | multipart 提交成果（文字 + 可选照片，进入审核流） |
| GET | `/api/learning/notifications/unread` | 学生 | 未读通知数与列表（WS 断线降级轮询用） |

## 14. 成长农场 `/api/farm`（学生端）

> 能量经济：学习任务审核通过 +10 ⚡、打卡审核通过 +5 ⚡；开通时历史已审核成果一次性回填（`backfilled` 守卫去重）。
> 消耗：种菜 -20（120 分钟成熟，收获 +30）、养殖 -50（480 分钟长成，收获 +80）、浇树 -50/次。
> 成长树累计注入 1500 能量育成大树：森林 +1、成长树归零循环；阶段门槛 100/400/900，地块上限 = 4 + 阶段 + 森林数。
> 未开通时调用任何操作接口返回 400；实时钩子在无农场/未回填时静默跳过（能量不丢失）。

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/farm/status` | 学生 | 农场总览；未开通时返回模板清单 + 站点默认名 + 能量规则 |
| GET | `/api/farm/templates` | 学生 | 启用中的农场模板（田园/科幻/卡通） |
| POST | `/api/farm/init` | 学生 | 开通农场（body: [name]≤32, [template_key]），历史能量一次性回填 |
| PUT | `/api/farm/rename` | 学生 | 个性化改名（body: name 1-32 字符） |
| PUT | `/api/farm/template` | 学生 | 切换模板（停用模板 400，已种地块不受影响） |
| POST | `/api/farm/plant` | 学生 | 种植/领养（body: plot_type=crop\|animal, item_key；模板外素材/能量不足/地块满 400） |
| POST | `/api/farm/harvest/{plot_id}` | 学生 | 收获（未成熟/重复收获 400；他人地块 404 防探测） |
| POST | `/api/farm/water` | 学生 | 浇树（-50 ⚡，阶段提升/育成大树发通知） |
| GET | `/api/farm/energy-log` | 学生 | 能量流水（分页，最新在前；含来源/变动/余额/备注） |

> **提示**：`points-system`（端口 8001）为独立系统，其奖品接口为 `/api/prizes`（非 `/api/products`），健康检查同为 `/api/health`。
