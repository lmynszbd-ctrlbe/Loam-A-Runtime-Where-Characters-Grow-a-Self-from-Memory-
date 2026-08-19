# loam 最终版启动（Termux）

## 先说“配好上游”是什么意思

你在 Agent 里改了 URL 到本地代理后，代理必须知道：
- 要转发到哪几家中转
- 每家的 key 是什么
- 每家默认模型是啥

这份映射文件就是：`~/.loam/upstreams.json`

如果还没配，先执行：

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
```

再把里面的 `base_url/api_key/default_model` 改成你的真实配置。

---

## 一条命令（多上游推荐）

```bash
cd ~/loam && \
LOAM_API_KEY='你的loam后台key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

启动顺序（脚本内部自动执行）：
1. 启动 loam
2. 启动 forced proxy
3. 检查 loam `/health`
4. 检查 proxy `/health` + `/v1/models`

---

## 一条命令（单上游）

```bash
cd ~/loam && \
LOAM_API_KEY='你的loam后台key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAM_BASE_URL='你的中转URL' \
UPSTREAM_API_KEY='你的中转key' \
UPSTREAM_MODEL='你的默认模型' \
bash scripts/termux/final_start_all.sh
```

---

## Agent 里怎么填

- Base URL: `http://127.0.0.1:8780/v1`
- API Key: 任意占位（若客户端强制）
- 模型：
  - 多上游：`provider/model`
  - 单上游：普通模型名

---

## 管理命令

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
bash scripts/termux/final_stop_all.sh
```

---

## 核心原则回顾（避免跑偏）

- loam 的人格演化锚在 **L0 原始对话**，不是锚在“上一版总结”
- 这就是“不是滚雪球”的关键
- 换模型、换上游，都不该破坏原始记忆底座