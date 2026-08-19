# 多中转上游快速配置（forced proxy）

## 1) 准备上游配置文件

复制模板：

```bash
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
```

编辑 `~/.loam/upstreams.json`，填入你的多个中转：
- 每个 provider 一套 `base_url + api_key + default_model`
- `default` 指默认 provider

## 2) 启动 loam

```bash
cd ~/loam
LOAM_API_KEY='你的loam后台key' LOAM_MODEL='你的flash模型ID' bash scripts/termux/bootstrap_and_start.sh
```

## 3) 启动多上游代理

```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/start_forced_proxy.sh
```

## 4) 在 agent 软件里配置

- Base URL: `http://127.0.0.1:8780/v1`
- API Key: 任意占位（如果客户端强制要求）
- 模型：从 `/v1/models` 拉取后，选择 `provider/model` 形式

例子：
- `relayA/gpt-4o-mini`
- `relayB/claude-3-5-sonnet`
- `relayC/deepseek-chat`

## 5) 状态与停止

```bash
cd ~/loam
bash scripts/termux/status_forced_proxy.sh
bash scripts/termux/stop_forced_proxy.sh
```

---

> 你切模型就是切 provider/model，代理会自动把请求路由到对应中转。