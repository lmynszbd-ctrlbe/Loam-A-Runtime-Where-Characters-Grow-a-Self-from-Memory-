# loam 最终版启动（Termux）

## 一条命令（多上游推荐）

> 前提：你已把 `~/.loam/upstreams.json` 配好（可从 `bridge/upstreams.example.json` 复制）

```bash
cd ~/loam && \
LOAM_API_KEY='你的loam后台key' \
LOAM_MODEL='你的flash模型ID' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

启动顺序（脚本内部自动执行）：
1. 启动 loam
2. 启动 forced proxy
3. 检查 loam /health
4. 检查 proxy /health + /v1/models

---

## 一条命令（单上游）

```bash
cd ~/loam && \
LOAM_API_KEY='你的loam后台key' \
LOAM_MODEL='你的flash模型ID' \
UPSTREAM_BASE_URL='你的中转URL' \
UPSTREAM_API_KEY='你的中转key' \
UPSTREAM_MODEL='你的默认模型' \
bash scripts/termux/final_start_all.sh
```

---

## Agent 里怎么填

- Base URL: `http://127.0.0.1:8780/v1`
- 模型：
  - 多上游：选 `provider/model`
  - 单上游：选你的普通模型名

---

## 管理命令

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
bash scripts/termux/final_stop_all.sh
```
