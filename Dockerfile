# ============================================================
# TTS 统一服务 Dockerfile
# 通过 SERVICE 构建参数选择要构建的服务：
#   docker build --build-arg SERVICE=teleai   -t tts-teleai .
#   docker build --build-arg SERVICE=edge-tts -t tts-edge .
#   docker build --build-arg SERVICE=sherpa   -t tts-sherpa .
# ============================================================
# 使用国内镜像（Docker Hub 在国内访问受限）
FROM docker.m.daocloud.io/library/python:3.11-slim

ARG SERVICE
ENV SERVICE=${SERVICE}

WORKDIR /app

# ---------- 系统依赖 ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python 依赖 ----------
# 使用清华 pip 镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY ${SERVICE}/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 通用依赖（所有服务都需要）
RUN pip install --no-cache-dir fastapi uvicorn[standard] requests

# ---------- 共享代码 ----------
COPY tts_common/ /app/tts_common/

# ---------- 服务代码 ----------
COPY ${SERVICE}/ /app/

# ---------- 启动 ----------
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
