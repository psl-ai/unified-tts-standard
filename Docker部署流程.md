# Docker 部署完整流程

## 背景

服务器 (172.31.8.3) 没有外网，Docker 构建时无法下载 Python 包。
所以要在本地（能上网）构建好镜像，导出成文件，传到服务器加载。

---

## 第一步：本地构建镜像

在**你的电脑**上，打开 PowerShell：

```powershell
cd D:\tts统一标准\tts

# 1. Edge TTS（端口 8001）
docker build -f edge-tts/Dockerfile -t tts-edge:v1 .

# 2. Tianyi（端口 8900）
docker build -f tianyi_tts/Dockerfile -t tts-tianyi:v1 .

# 3. Gateway（端口 9000）
docker build -f tts_gateway/Dockerfile -t tts-gateway:v1 .
```

---

## 第二步：导出镜像

```powershell
docker save tts-edge:v1 tts-tianyi:v1 tts-gateway:v1 -o D:\tts统一标准\tts-images.tar
```

---

## 第三步：上传到服务器

打开 xftp8，连接 172.31.8.3:2220，用户 zdsz。

把 `D:\tts统一标准\tts-images.tar` 拖到 `/home/zdsz/`

---

## 第四步：服务器加载镜像

SSH 连上服务器（xshell 或 PowerShell）：

```bash
ssh -p 2220 zdsz@172.31.8.3
```

```bash
# 加载镜像
docker load -i /home/zdsz/tts-images.tar

# 确认加载成功
docker images | grep tts
# 应看到: tts-edge:v1, tts-tianyi:v1, tts-gateway:v1
```

---

## 第五步：启动容器

```bash
# Edge TTS
docker run -d --name tts-edge --restart always -p 8001:8001 tts-edge:v1

# Tianyi
docker run -d --name tts-tianyi --restart always -p 8900:8900 tts-tianyi:v1

# Gateway
docker run -d --name tts-gateway --restart always -p 9000:9000 tts-gateway:v1

# 确认都在跑
docker ps | grep tts
```

---

## 第六步：测试

在你电脑上：

```powershell
# 健康检查
python -c "import requests; [print(f'{n}:', requests.get(f'http://172.31.8.3:{p}/health', headers={'X-API-Key':'my-fixed-key-2026'}).status_code) for p,n in [(8001,'Edge'),(8900,'Tianyi'),(9000,'Gateway')]]"

# Gateway → Edge
python -c "import requests; r=requests.post('http://172.31.8.3:9000/tts/edge', json={'text':'你好'}, headers={'X-API-Key':'my-fixed-key-2026'}); print(r.status_code)"

# Gateway → Tianyi
python -c "import requests; r=requests.post('http://172.31.8.3:9000/tts/supernatural', json={'text':'你好','voice':'xianliaonv'}, headers={'X-API-Key':'my-fixed-key-2026'}); print(r.status_code)"
```

---

## 以后更新代码

### 改了什么？分两种情况：

**只改了 Python 代码，没改依赖**：

1. 本地修改代码
2. xftp8 把改过的文件替换到服务器对应位置
3. 重建镜像（不需要网络，因为 pip 层有缓存）还是重新传最快

最快方式：直接重新走一遍第一步到第四步。

**改了依赖（requirements.txt）**：

1. 改 Dockerfile
2. 重新走一遍第一步到第四步

---

## 常用命令

```bash
# 查看容器日志
docker logs tts-edge
docker logs tts-tianyi

# 查看启动 Token
docker logs tts-edge 2>&1 | grep "API Token"

# 重启某个服务
docker restart tts-edge

# 停掉所有
docker stop tts-edge tts-tianyi tts-gateway
docker rm tts-edge tts-tianyi tts-gateway
```
