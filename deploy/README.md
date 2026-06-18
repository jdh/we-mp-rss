# We-MP-RSS 云服务器部署指南

## 一、本地构建镜像

### 1. 执行构建脚本
```bash
cd /path/to/we-mp-rss
chmod +x build-docker.sh
./build-docker.sh
```

构建完成后会生成：
- Docker 镜像：`we-mp-rss:latest`
- 镜像文件：`we-mp-rss-latest.tar`

---

## 二、上传到云服务器

### 方式一：使用 scp 上传
```bash
scp we-mp-rss-latest.tar root@your-server-ip:/root/we-mp-rss/
```

### 方式二：使用 rsync （支持断点续传）
```bash
rsync -avz --progress we-mp-rss-latest.tar root@your-server-ip:/root/we-mp-rss/
```

---

## 三、云服务器部署

### 1. 上传 deploy 目录到服务器
将整个 `deploy/` 目录上传到云服务器：
```bash
scp -r deploy/* root@your-server-ip:/root/we-mp-rss/
```

### 2. 登录云服务器
```bash
ssh root@your-server-ip
cd /root/we-mp-rss
```

### 3. 导入Docker镜像
```bash
docker load -i we-mp-rss-latest.tar
```

### 4. 配置环境变量
```bash
cp .env.example .env
nano .env  # 编辑配置，修改密码等敏感信息
```

### 5. 执行部署脚本
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 四、常用运维命令

### 查看服务状态
```bash
docker compose ps
```

### 查看日志
```bash
# 查看所有日志
docker compose logs -f

# 查看指定服务日志
docker compose logs -f we-mp-rss
docker compose logs -f mysql
```

### 重启服务
```bash
docker compose restart
```

### 停止服务
```bash
docker compose down
```

### 更新镜像
```bash
# 1. 停止服务
docker compose down

# 2. 导入新镜像
docker load -i we-mp-rss-latest.tar

# 3. 重新启动
docker compose up -d
```

---

## 五、目录结构

```
we-mp-rss/
├── docker-compose.yaml    # 服务编排配置
├── .env                   # 环境变量配置
├── .env.example           # 配置模板
├── deploy.sh              # 部署脚本
├── README.md              # 本文档
├── data/                  # 应用数据目录（自动创建）
└── mysql/
    ├── data/              # MySQL数据目录（自动创建）
    └── init/              # MySQL初始化脚本
```

---

## 六、安全建议

1. **修改默认密码**：务必修改 `.env` 中的所有默认密码
2. **防火墙配置**：只开放必要端口（8001）
3. **定期备份**：定期备份 `data/` 和 `mysql/data/` 目录
4. **使用HTTPS**：建议配置Nginx反向代理并启用HTTPS

---

## 七、Nginx 反向代理配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时配置
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```
