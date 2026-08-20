# loam 超详细部署手册（零基础可跟着做）

> 这份文档是给“几乎不懂代码”的用户准备的。
> 你只要按步骤复制命令，照着检查结果，就能部署成功。

---

## 0. 先说人话：你到底在部署什么？

loam 实际上有两个服务：
1. **loam 服务**（默认 8765 端口）
   - 负责记忆、消化、生长、上下文。
2. **forced proxy 代理**（默认 8780 端口）
   - 你的客户端连接它。
   - 它会强制执行：`/context -> 上游模型 -> /ingest`。

你在客户端里最终填写的是：
- Base URL: `http://127.0.0.1:8780/v1`
- 模型名：`provider/model`（例如 `relayA/gpt-4o-mini`）

---

## 1. 你先选部署模式（只选一个先跑通）

- **A. Android + Termux（最推荐新手）**
  - 最快，步骤最少，适合个人常驻。
- **B. Linux / WSL / macOS（电脑部署）**
  - 稳定、适合长期运行。
- **C. Docker（团队/环境一致）**
  - 适合希望“别人一拉就能跑”的场景。

如果你只是第一次跑通：**先做 A（Termux）**。

---

## 2. 通用准备（所有模式都需要）

你至少需要一个上游模型提供方账号（或中继）：
- `base_url`
- `api_key`
- `default_model`

没有这些，代理虽然能启动，但聊天不会成功。

## 2.1 什么是“上游模板”？（第一次部署必看）

你在文档里看到的“上游模板”，指的是仓库里的**示例文件**：
- `~/loam/bridge/upstreams.example.json`

> 如果你仓库不在 `~/loam`，把路径换成你实际克隆目录。

它的本质是“可复制的 JSON 样板”：
- 里面的 `sk-xxx`、`example.com` 都是占位值，不能直接用。
- 你要把它复制成自己的运行配置文件：`~/.loam/upstreams.json`。
- forced proxy 真正读取的是 `~/.loam/upstreams.json`，不是示例文件本身。

你可以先看模板长什么样（只读，不会修改）：

```bash
cat ~/loam/bridge/upstreams.example.json
```

字段含义（超简版）：
- `default`：当模型名没写 provider 前缀时，默认走哪个 provider。
- `providers.<name>.base_url`：上游 API 地址（通常以 `https://` 开头，不是官网首页）。
- `providers.<name>.api_key`：该上游的密钥。
- `providers.<name>.default_model`：该上游默认模型 ID。

---

# A) Android + Termux：一步一步（最详细）

## A-1. 安装 Termux

1. 安装 Termux（建议 F-Droid 版本）。
2. 打开 Termux，看到提示符（通常是 `$`）即成功。

## A-2. 给 Termux 存储权限（很重要）

在 Termux 里执行：

```bash
termux-setup-storage
```

- 手机会弹权限框，点允许。
- 成功后不会报错。

## A-3. 安装基础工具

```bash
pkg update -y
pkg install -y python git curl nano
```

你应该看到：
- 安装完成
- 回到提示符

## A-4. 下载仓库

```bash
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

如果提示目录已存在，执行：

```bash
cd ~/loam
git pull
```

## A-5. 创建上游配置文件（重点）

这一步里的“上游模板”就是仓库中的示例文件：`~/loam/bridge/upstreams.example.json`。
你要做的是：复制模板 → 生成自己的 `~/.loam/upstreams.json` → 再把占位值改成真实值。

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

打开后，把占位值改成你的真实值。这三个值通常在上游模型服务商的「API / 开发者 / 密钥管理」页面能找到：
- `base_url`：服务商提供的 API 地址（以 https:// 开头）。注意：不要填成官网首页地址。
- `api_key`：在服务商后台新建的密钥。注意：不要发给别人，也不要提交到 GitHub。
- `default_model`：服务商支持的模型 ID，要原样复制，区分大小写。

最小示例：

```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://your-upstream.example.com",
      "api_key": "sk-xxxx",
      "default_model": "gpt-4o-mini"
    }
  }
}
```

保存 nano：
- `Ctrl + O`（写入）
- 回车确认
- `Ctrl + X`（退出）

可选但推荐：立刻检查 JSON 语法是否正确（输出 `JSON_OK` 才算通过）：

```bash
python -m json.tool ~/.loam/upstreams.json >/dev/null && echo JSON_OK
```

## A-6. 一键启动 loam + proxy

```bash
cd ~/loam
LOAM_API_KEY='你的内部生长模型key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

如果启动成功，你会看到健康检查输出（或成功提示）。

## A-7. 验证服务是否真的活着

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

你应该看到：
- `/health` 返回 JSON，且 `ok: true`
- `/v1/models` 里有模型列表（最好带 provider 前缀）

## A-8. 在客户端填写参数

客户端填写：
- Base URL：`http://127.0.0.1:8780/v1`
- API Key：如果客户端强制非空，随便填一个占位字符串（如 `local-key`）
- Model：`relayA/xxx`（例如 `relayA/gpt-4o-mini`）

## A-9. 日常命令

查看状态：
```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
```

停止服务：
```bash
cd ~/loam
bash scripts/termux/final_stop_all.sh
```

更新代码并重启：
```bash
cd ~/loam
git pull
bash scripts/termux/final_stop_all.sh
bash scripts/termux/final_start_all.sh
```

---

# B) Linux / WSL / macOS：一步一步

## B-1. 安装基础依赖

### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip git curl nano
```

### macOS（Homebrew）
```bash
brew install python git curl
```

### WSL
在 Ubuntu 子系统里按 Ubuntu 步骤安装即可。

## B-2. 下载仓库

```bash
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

## B-3. 创建上游映射

和 Termux 一样，这里的“上游模板”也是仓库示例文件：`~/loam/bridge/upstreams.example.json`。
复制后编辑 `~/.loam/upstreams.json`，把占位值换成你自己的真实参数。

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

编辑方式与 Termux 一样（同上示例）。编辑后建议立刻校验 JSON：

```bash
python -m json.tool ~/.loam/upstreams.json >/dev/null && echo JSON_OK
```

## B-4. 启动 loam（终端1）

```bash
cd ~/loam
python -m loam init-secrets --secrets-home ~/.loam
python -m loam run --character default --home ~/.loam/characters --secrets-home ~/.loam --host 127.0.0.1 --port 8765
```

这个终端保持运行，不要关。

## B-5. 启动 proxy（终端2）

```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' python bridge/forced_flow_proxy.py
```

这个终端也保持运行。

## B-6. 验证

在第三个终端执行：

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

如果都正常，再去客户端填 Base URL 和模型名。

---

# C) Docker：一步一步

## C-1. 安装 Docker / Docker Compose

先确认命令可用：

```bash
docker --version
docker compose version
```

## C-2. 进入项目目录

```bash
cd ~/loam
```

## C-3. 准备本地数据目录

```bash
mkdir -p ./data
```

## C-4. 启动容器

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

## C-5. 验证

```bash
curl -s http://127.0.0.1:8765/health
```

## C-6.（可选）把 proxy 链路也接上

`docker compose` 这份默认配置只启动 loam，不会自动启动 forced proxy。
如果你希望客户端走完整链路（`/context -> upstream -> /ingest`），还需要单独准备上游配置并启动 proxy：

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
python -m json.tool ~/.loam/upstreams.json >/dev/null && echo JSON_OK

cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' python bridge/forced_flow_proxy.py
```

然后再验证：

```bash
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

---

## 3. 常见报错与“照抄修复”

### 报错 1：`models 为空`
原因：`~/.loam/upstreams.json` 填错。

修复：
1. 重新打开文件检查 JSON 语法。
2. 检查 `base_url/api_key/default_model`。
3. 重启服务。

### 报错 2：`unauthorized` / 401
原因：启用了 API Key 鉴权但请求没带 key。

修复：
- 在请求头加 `X-API-Key` 或 `Authorization: Bearer xxx`。

### 报错 3：`connection refused`
原因：服务没启动、端口错、进程退出。

修复：
1. 检查是否有启动日志。
2. `curl /health` 看是否可访问。
3. 查看日志文件定位崩溃原因。

### 报错 4：Termux 启动后马上退出
修复：
- 查看 `~/.loam/run/forced_proxy.log`
- 通常是 upstream 配置文件错误。

---

## 4. 一键健康检查清单（你可以直接照抄）

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/healthz
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

判断标准：
- 至少 `/health` 返回 JSON 且 `ok=true`
- `/v1/models` 非空

---

## 5. 部署后建议做的三件事

1. 立刻做一次快照备份：
```bash
python scripts/ops/create_snapshot.py --character-dir ~/.loam/characters/default --out-dir ~/.loam/backups
```

2. 跑一次演练脚本（确认流水线端到端正常）：
```bash
python scripts/ops/load_and_fault_drill.py --base-url http://127.0.0.1:8765 --sessions 2 --turns 5 --fault-check
```

3. 保存你成功时的配置文件副本（脱敏后）。

---

## 6. 你卡住时，发给维护者这 6 样信息

1. 你用的模式（Termux / Linux / Docker）
2. 你执行到哪一步（例如 A-6）
3. 出错命令原文
4. 终端完整报错
5. `curl /health` 输出
6. （可脱敏）`upstreams.json` 结构

这样排障会快很多。