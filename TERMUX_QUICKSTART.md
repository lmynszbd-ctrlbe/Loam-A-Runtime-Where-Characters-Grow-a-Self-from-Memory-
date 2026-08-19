# loam on Termux（一步启动 + 持续运行）

## 0) 先装依赖

```bash
pkg update -y
pkg install -y python curl
```

> 如果你要开机自启，再装并安装 **Termux:Boot** App。

## 1) 一键启动（必须提供 key/model）

在项目目录执行（假设仓库在 `~/loam`）：

```bash
cd ~/loam
LOAM_API_KEY='你的DeepSeekKey' \
LOAM_MODEL='你的flash模型ID' \
bash scripts/termux/bootstrap_and_start.sh
```

- `LOAM_MODEL` 建议填你指定的 flash 模型
- 会写入 `~/.loam/secrets.json`
- 服务默认监听 `127.0.0.1:8765`

## 2) 常用管理命令

```bash
cd ~/loam
bash scripts/termux/status_loam.sh   # 看状态+health
bash scripts/termux/log_loam.sh      # 看日志
bash scripts/termux/stop_loam.sh     # 停止
bash scripts/termux/start_loam.sh    # 启动
```

## 3) 开机自启（可选）

```bash
cd ~/loam
bash scripts/termux/install_boot.sh
```

然后重启手机验证：

```bash
bash scripts/termux/status_loam.sh
```

## 4) 快速接口检查

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/stats
```

如果有返回 JSON，说明服务持续运行正常。