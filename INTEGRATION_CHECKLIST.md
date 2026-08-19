# loam Pre-Launch Integration Checklist

Use this checklist before production rollout to verify runtime, routing, growth behavior, and data safety.
上线前请按本清单验证运行时、路由、生长行为和数据安全。

---

## A) Runtime and boot checks

Confirm CLI availability (`python -m loam --help`), ensure service can start with your selected character/home/secrets path, and verify that `/health` endpoints for both loam and proxy return valid JSON. If startup depends on process managers, validate restart-on-failure behavior before launch.

确认 CLI 可用（`python -m loam --help`），确保服务能在你指定的 character/home/secrets 路径启动，并验证 loam 与 proxy 的 `/health` 都返回有效 JSON。如果依赖进程管理器托管，请在上线前验证故障自动拉起。

---

## B) Routing and model checks

Validate `~/.loam/upstreams.json` syntax, ensure default provider exists, and confirm `/v1/models` returns provider-prefixed model ids (for example `relayA/gpt-4o-mini`). Send at least one real chat request through proxy and verify traffic reaches expected upstream provider.

验证 `~/.loam/upstreams.json` 语法正确、默认 provider 存在，并确认 `/v1/models` 返回带 provider 前缀的模型 id（如 `relayA/gpt-4o-mini`）。至少通过 proxy 发起一次真实聊天请求，确认流量命中预期上游。

---

## C) Memory pipeline checks

Run one full turn and verify forced sequence `/context -> upstream -> /ingest` completes. Check loam stats for memory/event growth and confirm raw turn write happened even when summary-like tools are not called by host platform.

执行至少一轮完整请求并验证强制序列 `/context -> upstream -> /ingest` 完成。检查 loam stats 的记忆/事件增长，确认即使宿主平台未调用摘要类工具，原始轮次也已写入。

---

## D) Growth behavior checks

With repeated staged inputs, verify trait movement is progressive (not random spikes), pending accumulation behaves as expected, and qualitative shifts happen only after gate crossing. For important scenarios, run controlled probes and archive baseline outputs.

通过分阶段重复输入，验证特质变化是渐进的（而非随机暴冲）、pending 累积符合预期、质变只在跨门槛后发生。关键场景建议跑受控探针并保存基线输出。

---

## E) Data safety and rebuild checks

Verify raw journal remains readable, derived-layer reset does not destroy immutable raw material, and digestion reset can replay historical raw turns to regenerate derived memory. This ensures long-term maintainability after model or policy upgrades.

验证原始 journal 可读，派生层重置不会破坏不可变原料，digest 重置后可重放历史原始轮次并再生成派生记忆。这是模型或策略升级后保持可维护性的关键保障。

---

## F) Security boundary checks

Confirm provider keys are sourced from local files/environment and are not hardcoded in repository files. Verify remote origin URL does not include tokens and ensure release text or docs do not accidentally expose credentials.

确认 provider key 来自本地文件/环境变量，而非硬编码进仓库文件。验证 remote URL 不包含 token，并检查发布文案与文档中没有误泄露凭证。

---

## G) Regression smoke set (recommended commands)

Use a minimum smoke set before release: `python tests/test_growth.py`, `python tests/test_context.py`, `python tests/test_server.py`, and one end-to-end run with real upstream credentials. Store output logs as release evidence.

上线前建议至少执行以下冒烟集合：`python tests/test_growth.py`、`python tests/test_context.py`、`python tests/test_server.py`，以及一次带真实上游凭证的端到端运行。请保存输出日志作为发布证据。