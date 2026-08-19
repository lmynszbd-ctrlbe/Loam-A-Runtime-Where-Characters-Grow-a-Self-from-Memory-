# 多中转上游快速配置（forced proxy）

> 这份文档专门回答：**“什么叫配好上游？”**

## 0) 概念先说清

- 你在 Agent 里只配一个入口：`http://127.0.0.1:8780/v1`
- 但代理需要知道“背后有哪些中转可用”，这份映射就叫 **上游配置**
- 上游配置文件路径：`~/.loam/upstreams.json`

---

## 1) 复制模板

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
```

---

## 2) 编辑上游配置（核心）

`~/.loam/upstreams.json` 示例：

```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://relay-a.example.com",
      "api_key": "sk-xxxx",
      "default_model": "gpt-4o-mini"
    },
    "relayB": {
      "base_url": "https://relay-b.example.com",
      "api_key": "sk-yyyy",
      "default_model": "claude-3-5-sonnet"
    },
    "relayC": {
      "base_url": "https://relay-c.example.com",
      "api_key": "sk-zzzz",
      "default_model": "deepseek-chat"
    }
  }
}
```

字段说明：
- `default`：默认 provider 名字（例如 `relayA`）
- `providers.<name>.base_url`：这家中转的 OpenAI 兼容基址
- `providers.<name>.api_key`：对应 key
- `providers.<name>.default_model`：当只写 provider 时默认走的模型

---

## 3) 启动 loam（后台生长）

```bash
cd ~/loam
LOAM_API_KEY='你的loam后台key' \
LOAM_MODEL='deepseek-chat-flash' \
bash scripts/termux/start_loam.sh
```

---

## 4) 启动 forced proxy（多上游路由）

```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/start_forced_proxy.sh
```

---

## 5) 在 Agent 软件里怎么填

- Base URL: `http://127.0.0.1:8780/v1`
- API Key: 任意占位（如果客户端强制要求）
- 模型：`provider/model`

示例：
- `relayA/gpt-4o-mini`
- `relayB/claude-3-5-sonnet`
- `relayC/deepseek-chat`

这就实现了：**一个 URL，切多家渠道。**

---

## 6) 验证是否“配好上游”

```bash
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

- `/health` 返回 ok：代理活着
- `/v1/models` 能看到 `provider/model` 列表：上游映射生效

---

## 7) 常见错误

- `~/.loam/upstreams.json` 路径写错
- `base_url` 不是 OpenAI 兼容接口
- key 填错或过期
- 模型名不匹配（比如上游叫 `deepseek-chat`，你却写了别的）

---

## 8) 管理命令

```bash
cd ~/loam
bash scripts/termux/status_forced_proxy.sh
bash scripts/termux/stop_forced_proxy.sh
```