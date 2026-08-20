FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# loam 仅依赖标准库；这里不安装第三方包。
RUN python -m compileall -q loam

EXPOSE 8765
VOLUME ["/data"]

CMD [
  "python",
  "-m",
  "loam",
  "run",
  "--host",
  "0.0.0.0",
  "--port",
  "8765",
  "--character",
  "demo",
  "--home",
  "/data/characters"
]