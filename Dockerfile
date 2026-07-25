# syntax=docker/dockerfile:1

FROM python:3.14.6-slim-bookworm

# 镜像元数据
LABEL org.opencontainers.image.title="PowerAgent"
LABEL org.opencontainers.image.description="面向动力系统数智化管理的多Agent工作流平台"
LABEL org.opencontainers.image.version="0.1.0"

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HOME=/home/poweragent

WORKDIR /app

# 创建非root运行用户以及需要写入的目录。
RUN groupadd \
        --gid 10001 \
        poweragent \
    && useradd \
        --uid 10001 \
        --gid poweragent \
        --create-home \
        --home-dir /home/poweragent \
        --shell /usr/sbin/nologin \
        poweragent \
    && mkdir -p \
        /app/data/chroma \
        /app/data/uploads/tmp \
        /app/logs \
        /home/poweragent/.cache \
    && chown -R \
        poweragent:poweragent \
        /app \
        /home/poweragent

# 先复制依赖文件，充分利用Docker构建缓存。
COPY requirements.txt ./requirements.txt

RUN python -m pip install \
        --no-cache-dir \
        --requirement requirements.txt

# 仅复制API运行所需的生产代码。
COPY --chown=poweragent:poweragent \
    agent_core \
    ./agent_core

COPY --chown=poweragent:poweragent \
    app \
    ./app

COPY --chown=poweragent:poweragent \
    rag \
    ./rag

COPY --chown=poweragent:poweragent \
    report \
    ./report

COPY --chown=poweragent:poweragent \
    skills \
    ./skills

COPY --chown=poweragent:poweragent \
    workflows \
    ./workflows

# 构建阶段执行一次模块导入检查。
RUN python -c \
    "from app.main import create_app; application = create_app(); print(application.title)"

USER poweragent

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=45s \
    --retries=5 \
    CMD [ \
        "python", \
        "-c", \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5).read()" \
    ]

CMD [ \
    "python", \
    "-m", \
    "uvicorn", \
    "app.main:app", \
    "--host", \
    "0.0.0.0", \
    "--port", \
    "8000", \
    "--workers", \
    "1", \
    "--no-access-log" \
]