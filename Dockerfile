FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=5000 _RUN_TYPE=WEB MPLCONFIGDIR=/tmp \
    FORWARDED_ALLOW_IPS=127.0.0.1,172.17.0.1
WORKDIR /app

# ==================== 👇 核心修改在这里 👇 ====================
# 安装 FFmpeg 系统依赖
# update: 更新源
# install: 安装 ffmpeg
# --no-install-recommends: 不安装推荐的额外包，保持镜像体积小
# rm -rf: 安装完清理缓存，减小镜像体积
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*
# ============================================================

# 如需 graphviz/字体再放开（可选）
# RUN apt-get update && apt-get install -y --no-install-recommends graphviz fonts-dejavu-core \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码
COPY app/ /app/app/
COPY common/ /app/common/
COPY data/dependency/ /app/data/dependency/
COPY serve.py /app/serve.py
COPY gunicorn_config.py /app/gunicorn_config.py

# 非 root 运行
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 5000
CMD ["gunicorn", "-c", "gunicorn_config.py", "serve:app"]

