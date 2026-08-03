# HTTPS 启用指南（V-01 整改配套）

当前状态：**未启用**。仓库中只有配置模板 [`https.conf.example`](./https.conf.example)，
它不被任何 nginx 配置加载，因此对现有 HTTP 环境零影响。

## 前置条件：必须先有域名

Let's Encrypt **不为裸 IP 地址签发证书**。生产当前通过 `http://<IP>:<端口>/homework/`
访问，因此启用 HTTPS 前必须先完成：

1. 准备一个域名（如 `homework.example.com`）
2. 添加 A 记录指向生产服务器公网 IP
3. 确认服务器 80 端口可从公网访问（ACME HTTP-01 校验需要）

若暂时没有域名，可用自签证书先验证配置链路是否正确（浏览器会显示证书告警，
不能用于正式使用）：

```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout nginx/certs/privkey.pem -out nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

此时需注释掉模板中的 `ssl_stapling` 三行（自签证书没有 OCSP 链）。

## 启用步骤

### 1. 签发证书（certbot webroot 模式）

```bash
# 在服务器上执行，DOMAIN 替换为实际域名
DOMAIN=homework.example.com
mkdir -p /var/www/certbot
docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/www/certbot:/var/www/certbot \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --agree-tos -m admin@example.com --non-interactive
```

证书签发后位于 `/etc/letsencrypt/live/$DOMAIN/`。

### 2. 修改配置模板

```bash
cp nginx/https.conf.example nginx/https.conf
# 把模板中所有 example.com 替换为实际域名
sed -i '' "s/example\.com/$DOMAIN/g" nginx/https.conf
```

### 3. 调整 nginx 编排

编辑 [`nginx/docker-compose.yml`](./docker-compose.yml)，做三处改动：

```yaml
    ports:
      - "80:80"
      - "443:443"          # 新增
    volumes:
      # 用 https.conf 取代 default.conf（两者都定义 default_server，不能同时挂载）
      - ./https.conf:/etc/nginx/conf.d/default.conf:ro
      - ./sites:/etc/nginx/sites:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro          # 新增：证书
      - /var/www/certbot:/var/www/certbot:ro          # 新增：ACME 续期校验目录
```

> 关键：`https.conf` 挂载到 `conf.d/default.conf` 路径，而不是放进 `sites/`。
> `sites/*.conf` 会被 `include` 到 default.conf 的 **server 块内部**，
> 放 server 块进去会导致 nginx 启动失败（`"server" directive is not allowed here`）。

### 4. 校验并生效

```bash
docker compose -f nginx/docker-compose.yml up -d
docker exec local-nginx nginx -t          # 先校验语法
docker exec local-nginx nginx -s reload   # 通过后热重载
```

### 5. 配置自动续期

Let's Encrypt 证书有效期 90 天。在服务器上加 crontab：

```bash
# 每月 1 日 3:30 尝试续期，成功则重载 nginx
30 3 1 * * docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot certbot/certbot renew --quiet && docker exec local-nginx nginx -s reload
```

### 6. 同步更新应用侧配置

- `ALLOWED_ORIGINS` 改为 `https://$DOMAIN`（去掉 http 来源）
- 推送配置中的 `public_base_url`（若使用）改为 `https://$DOMAIN`

## 回滚

HTTPS 配置全部集中在挂载项上，回滚只需还原 `docker-compose.yml`
的 volumes/ports 到挂载 `default.conf` 的状态，然后：

```bash
docker compose -f nginx/docker-compose.yml up -d
```

⚠️ 唯一不可逆的部分是 **HSTS**：`Strict-Transport-Security` 一旦下发，
浏览器在 `max-age`（模板中为 1 年）内会拒绝以 HTTP 访问该域名，即使服务端已回退。
建议首次启用时先把 `max-age` 调小（如 `max-age=300`）验证一段时间，
确认证书续期链路稳定后再改为 31536000。
