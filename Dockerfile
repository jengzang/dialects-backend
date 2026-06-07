FROM --platform=linux/amd64 python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    PORT=5000 _RUN_TYPE=WEB MPLCONFIGDIR=/tmp \
    NUMBA_THREADING_LAYER=omp \
    FORWARDED_ALLOW_IPS=127.0.0.1,172.17.0.1 \
    AUTO_MIGRATE=true \
    MIGRATION_TIMEOUT=300 \
    TZ=Asia/Shanghai
WORKDIR /app

# 如需 graphviz/字体再放开（可选）
# RUN apt-get update && apt-get install -y --no-install-recommends graphviz fonts-dejavu-core \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel scikit-build && \
    pip install --no-cache-dir --no-build-isolation -r requirements.txt

# 再补运行时依赖，降低单次 apt 事务的峰值内存占用
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    tzdata \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# 拷贝源码
COPY app/ /app/app/
COPY data/dependency/ /app/data/dependency/
COPY serve.py /app/serve.py
COPY gunicorn_config.py /app/gunicorn_config.py

# 非 root 运行
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 5000
CMD ["gunicorn", "-c", "gunicorn_config.py", "serve:app"]
