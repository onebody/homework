# 最佳实践与踩坑详解

真实项目中验证过的做法与代价换来的教训。

## 认证与权限

### 密钥管理三级策略（config.py）

优先级：环境变量 > `.secret_key` 落盘文件 > 首次自动生成并落盘。

```python
if os.environ.get("SUMMER_SECRET"):
    _raw = os.environ["SUMMER_SECRET"]
    # 拒绝弱密钥：常见弱词 / 长度不足 / 字符多样性过低（疑似重复字符）
    if _raw.lower() in {"changeme", "secret", "test"} or len(_raw) < 32:
        raise RuntimeError("SECRET 强度不足，请用 openssl rand -hex 32 生成")
    if len(set(_raw)) < 8:
        raise RuntimeError("SECRET 熵不足")
    SECRET = _raw
elif os.path.exists(_SECRET_FILE):
    SECRET = open(_SECRET_FILE).read().strip()
else:
    SECRET = secrets.token_hex(32)
    open(_SECRET_FILE, "w").write(SECRET)  # 落盘保证重启后 token 不失效
```

要点：**弱密钥直接拒绝启动**（fail-fast），而不是打警告继续跑。

### 角色权限依赖注入（deps.py）

```python
def require_role(*roles: str):
    def checker(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "无权限")
        return user
    return checker

# 用法：router 参数声明即完成鉴权
@router.get("/api/admin/users")
def list_users(admin=Depends(require_role("admin"))): ...
```

### 状态机防重复操作

审核/发放类操作先校验当前状态，非法转换返回 400：

```python
if record.status != "pending":
    raise HTTPException(400, "该记录已处理，不可重复操作")
```

同时落审计三件套：`reviewed_by`（操作者ID）、`reviewed_at`、`review_note`。

## 数据验证与错误处理

- 入参全走 Pydantic schema，路径/查询参数用类型注解约束
- service 层抛业务异常（自定义或 ValueError），router 统一转 HTTPException，禁止裸 500 透出堆栈
- 涉及积分/余额的扣减：先校验余额充足，扣减与记录创建在同一事务提交
- 拒绝/取消类操作要考虑逆向补偿（如拒绝兑换需退还积分）

## 时间处理（高频踩坑）

**offset-naive 与 offset-aware datetime 比较会直接 `TypeError`。** 全项目统一一种（推荐 naive UTC 存库，展示层转时区）。容器内设 `ENV TZ=Asia/Shanghai`（写进 Dockerfile，重建不丢），否则打卡日期会偏移 8 小时。

## 前端（Vue3 CDN 模式）

- 资源引用一律相对路径 `./app.js`——绝对路径在 Nginx 子路径（`/homework/`）下 404。这是本项目返工两次的教训
- API base 运行时计算：`location.pathname` 探测子路径前缀，前后端零配置适配
- 缓存刷新：发版改 `?v=YYYYMMDD` 版本参数，比教用户清缓存可靠
- CDN 选国内镜像（如 npmmirror），unpkg 直连不稳
- 移动端触控规范：可点击目标 ≥44px，输入框字号 ≥16px（否则 iOS 聚焦自动放大）

## SQLite 专项

- 开 WAL 模式提升并发读，但**备份必须用 `sqlite3.Connection.backup()`**：
  ```python
  src = sqlite3.connect("/data/app.db")
  dst = sqlite3.connect(f"/data/backups/app_{ts}.db")
  src.backup(dst)  # WAL 感知的一致性快照
  ```
  裸 `cp app.db` 会丢掉 `-wal` 文件里未 checkpoint 的最近事务。
- `.gitignore` 必须同时忽略 `*.db`、`*.db-wal`、`*.db-shm`
- 迁移三场景兜底（详见 templates/migrate.py.template）：全新库 create_all + stamp；有表无版本记录 stamp；正常 upgrade head

## 上传文件安全

1. 魔数校验（前几个字节判断真实类型），不信 Content-Type 和扩展名
2. 检测 SVG/HTML 伪装成图片（内容含 `<svg`/`<script` 拒绝）
3. 尺寸与大小上限；存储文件名用 uuid 重命名，不用原始文件名
4. 上传目录挂持久化卷，且在静态服务外通过鉴权接口访问敏感图片

## 敏感信息管理（提交前必查）

- 严禁明文密码/密钥进代码与 Git；一律环境变量或运行时生成
- 提交前扫描：`git diff HEAD | grep -E "密码值|密钥值|生产IP"` 确认无泄漏
- 部署脚本凭据全走环境变量（`DEPLOY_SSH_PASS` 等），SSH 密码用 `sshpass -e`（环境变量传递）避免进入 `ps` 可见的 argv
- `.gitignore` 分层：仓库根统一兜底（`*.db`/`.secret_key`/`.env*`/`uploads/`/`.backups/`），子项目再各自补充

## 容器安全

非 root 运行 + 属主自愈（完整文件见 templates/）：

- Dockerfile：`useradd --uid 10001 appuser`，预建 `/data` 并 chown——命名卷首次创建继承属主
- 入口脚本：root 启动时先 `chown -R appuser /data`（兼容 bind mount 属主错乱），再 `setpriv` 降权 exec
- 症状识别：bind mount 属主 root 时表现为启动崩溃循环或上传接口 500

## Git 仓库管理

- 生成物（数据库、上传文件、备份、venv、`__pycache__`、日志）全部忽略
- 提交信息用约定式前缀（feat/fix/docs），正文列出改动分组
- 演示性子项目可整目录忽略，避免污染主项目仓库
