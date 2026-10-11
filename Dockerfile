FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# loam 仅依赖标准库；这里不安装第三方包。
RUN python -m compileall -q loam

EXPOSE 8783
VOLUME ["/data"]

# The launcher starts core, proxy, admin, and the unified gateway. Only 8783
# is exposed; all other service ports stay inside the container.
ENV UNIFIED_HOST=0.0.0.0 \
    UNIFIED_PORT=8783 \
    LOAM_PORT=8765 \
    PROXY_PORT=8781 \
    ADMIN_PORT=8900 \
    LOAM_HOME=/data
CMD ["python", "start.py"]