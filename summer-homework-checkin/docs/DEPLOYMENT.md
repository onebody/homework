# 部署与运维指南

> 暑假作业打卡系统（三年级）· 部署、运维与故障排查
> 版本：v1.0 ｜ 最近更新：2026-07

---

## 一、部署方式总览

| 方式 | 适用场景 | 数据持久化 |
| --- | --- | --- |
| 本地开发（venv + uvicorn） | 开发调试 | `backend/app.db` + `backend/uploads/` |
| Docker Compose（推荐） | 本地/服务器一键部署 | 命名卷 `summer-data` / `points-data` |
| Nginx 反向代理 + Docker | 生产、子路径 `/homework/` | 同上 |

---

## 二、Docker Compose 部署（推荐）

编排文件位于仓库根目录 `docker-compose.yml`，同时启动主系统与积分系统。

```bash
# 在 hanghang_WS/ 根目录
docker compose up -d --build

# 访问：
#   学生端    http://localhost:8000/
#   管理端    http://localhost:8000/admin/
#   积分系统  http://localhost:8001/
```

### 服务与端口
| 服务 | 容器名 | 宿主端口 | 数据卷 |
| --- | --- | --- | --- |
| summer-homework | summer-homework | 8000→8000 | summer-data:/data |
| points-system | points-system | 8001→8000 | points-data:/data |

### 关键环境变量（summer-homework）
| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_PATH` | `/data/app.db` | SQLite 路径（指向持久化卷） |
| `UPLOAD_DIR` | `/data/uploads` | 上传目录（指向持久化卷） |
| `SUMMER_SECRET` | `summer-local-dev-secret` | Token 签名密钥，**生产务必改随机值** |
| `ALLOWED_ORIGINS` | `http://localhost:8000,...` | CORS 白名单 |
| `RATE_LIMIT_ENABLED` | `1` | 限流开关（0=关闭） |
| `ADMIN_INIT_PASSWORD` | 未设置则随机生成 | 管理员初始密码 |
| `MAX_MAKEUP_PER_MONTH` | `3` | 每月补卡上限 |
| `GEO_THRESHOLD_METERS` | `1500` | 地理风险阈值 |
| `FACE_MATCH_THRESHOLD` | `0.4` | 人脸相似度阈值 |
| `FACE_MODE_ON_ENROLLED` | `enforce` | 人脸不通过策略（enforce/soft） |
| `CHECKIN_POINTS` / `MAKEUP_POINTS` | `10` / `5` | 打卡/补卡积分 |

### 生产环境注入密钥示例
```bash
SUMMER_SECRET=$(openssl rand -hex 32) \
ADMIN_INIT_PASSWORD='your-strong-pass' \
docker compose up -d --build summer-homework
```

---

## 三、本地开发部署

```bash
cd summer-homework-checkin/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py                 # 建表 + 预设奖品 + 管理员
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
默认管理员账号 `admin`，首次启动生成随机密码（见控制台），或用 `ADMIN_INIT_PASSWORD` 指定。

---

## 四、Nginx 子路径部署（`/homework/`）

系统前端已内置子路径适配（`BASE_PATH` 自动检测 + 相对路径引用），无需改代码。Nginx 反向代理示例：

```nginx
location /homework/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

> **注意**：前端静态资源须为相对引用（`./app.js`、`./student.css`），Vue 使用国内可访问 CDN（`cdn.bootcdn.net`），避免公网子路径下 404 或 CDN 被墙导致模板未渲染（显示原始 `{{ }}`）。

---

## 五、镜像更新流程

```bash
# 1. 重建并滚动更新（数据卷不受影响）
docker compose up -d --build

# 2. 仅更新单个服务
docker compose up -d --build summer-homework

# 3. 查看状态与健康检查
docker compose ps
docker compose logs -f summer-homework

# 4. 离线服务器：本地导出→传输→加载
docker save hanghang_ws-summer-homework:latest | gzip > summer.tar.gz
scp summer.tar.gz user@server:/tmp/
ssh user@server 'gunzip -c /tmp/summer.tar.gz | docker load'
```

---

## 六、数据持久化与备份

- **持久化**：`DB_PATH` 与 `UPLOAD_DIR` 指向命名卷 `summer-data:/data`，容器重建/升级数据不丢失。
- **验证持久化**：
  ```bash
  docker compose exec summer-homework sh -c 'ls -la /data && du -h /data/app.db'
  ```
- **备份数据库**：
  ```bash
  docker compose exec summer-homework sh -c 'cp /data/app.db /data/backups/app-$(date +%F).db'
  # 或导出到宿主机
  docker cp summer-homework:/data/app.db ./backup-app.db
  ```
- **备份上传文件**：
  ```bash
  docker run --rm -v hanghang_ws_summer-data:/data -v "$PWD":/backup alpine \
    tar czf /backup/uploads-backup.tar.gz -C /data uploads
  ```
- **清空数据（谨慎）**：`docker compose down -v` 会删除数据卷。

---

## 七、健康检查与验收清单

部署后逐项确认（全部应为 200）：

```bash
# summer-homework
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/health   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/             # 学生端
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/app.js       # JS
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/student.css  # CSS
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/admin/       # 管理端
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/admin/app.js
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/admin/admin.css

# points-system
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8001/api/health   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8001/

# 登录 API
curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<密码>"}'
```

- [ ] 两个容器 `docker compose ps` 均为 `healthy`
- [ ] 所有静态资源返回 200（无 404）
- [ ] 登录返回 `access_token`
- [ ] `/data` 下 `app.db` 与 `uploads/` 存在且跨重启保留

---

## 八、常见故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 页面显示原始 `{{ }}` 模板 | Vue CDN 被墙未加载 | 确认使用国内 CDN（bootcdn），检查网络 |
| CSS/JS 404（子路径部署） | 使用了绝对路径引用 | 改为相对路径 `./xxx`，前端 `BASE_PATH` 生效 |
| `ERR_ADDRESS_UNREACHABLE` | 客户端网络/网段不通 | 服务器侧 curl 全 200 则为客户端问题，换网络/清缓存 |
| 打卡总被拒绝 | 人脸 enforce 模式 + 无模型 | 联网下载模型，或设 `FACE_MODE_ON_ENROLLED=soft` |
| 登录 429 | 触发限流 | 稍后重试，或测试环境 `RATE_LIMIT_ENABLED=0` |
| 重启后数据丢失 | 未挂载数据卷 / 用了 `down -v` | 确认 compose volumes 配置，勿用 `-v` |

---

## 九、生产建议

- **数据库**：SQLite 适合演示与小规模；正式环境建议 PostgreSQL/MySQL + 连接池。
- **服务**：uvicorn 多 worker（`--workers N`）或前置 Nginx；静态资源可托管至对象存储/CDN。
- **密钥**：`SUMMER_SECRET` 使用固定随机值并妥善保管，避免重启后 Token 失效。
- **人脸**：保障部署机联网（首次自动下载 buffalo_l，约 340MB 存于 `~/.insightface`），或预置模型；无外网自动降级安全模式。
- **通知**：当前为站内通知，可在 `notify_service` 扩展短信/微信模板消息渠道。
