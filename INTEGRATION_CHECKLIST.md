# loam Pre-Launch Integration Checklist

Use this checklist before public rollout.
上线前请完成本清单。

---

## A. Basic runtime
## A. 基础运行

- [ ] `python -m loam --help` prints usage correctly.
- [ ] `python -m loam --help` 正常输出帮助信息。

- [ ] `python -m loam stats --character demo --home <dir>` reads empty-store status.
- [ ] `python -m loam stats --character demo --home <dir>` 能读取空库状态。

- [ ] `python -m loam init-secrets --secrets-home ~/.loam` generates template.
- [ ] `python -m loam init-secrets --secrets-home ~/.loam` 能生成模板。

---

## B. End-to-end without key
## B. 无 key 端到端

- [ ] Run `python /home/loam/e2e_smoke.py` and see `✅ smoke ok`.
- [ ] 运行 `python /home/loam/e2e_smoke.py` 并看到 `✅ smoke ok`。

- [ ] After ingest, `pending > 0`.
- [ ] ingest 后 `pending > 0`。

- [ ] Without key, `digest_once` fails but `pending` is preserved.
- [ ] 无 key 时 `digest_once` 报错且 `pending` 不减少。

---

## C. End-to-end with key
## C. 有 key 端到端

- [ ] `~/.loam/secrets.json` contains `api_key/base_url/model`.
- [ ] `~/.loam/secrets.json` 已填 `api_key/base_url/model`。

- [ ] `model` is your required flash model id.
- [ ] `model` 使用你要求的 flash 模型 id。

- [ ] After ingest, `digest_once` reports `new_events > 0`.
- [ ] ingest 后 `digest_once` 出现 `new_events > 0`。

- [ ] `/context` returns non-empty recalled content.
- [ ] `/context` 返回非空 recalled 内容。

- [ ] `/stats` memory events grow with ongoing conversation.
- [ ] `/stats` 中事件数量随对话增长。

---

## C1. Growth validation (real model)
## C1. 生长验证（真实模型）

- [ ] Set `LOAM_API_KEY` and `LOAM_MODEL=<flash_model_id>`.
- [ ] 设置 `LOAM_API_KEY` 与 `LOAM_MODEL=<flash模型id>`。

- [ ] Run `python /home/loam/probe_growth_real_brain.py`.
- [ ] 运行 `python /home/loam/probe_growth_real_brain.py`。

- [ ] Check that trait strengths move by staged input design.
- [ ] 检查特质强度是否按阶段输入发生变化。

- [ ] If movement is too small, increase cycles to 20~30.
- [ ] 若变化过小，把循环提升到 20~30。

---

## D. Background grower
## D. 后台生长线程

- [ ] `auto_start_grower=true` starts autonomous digestion.
- [ ] `auto_start_grower=true` 时可自动消化。

- [ ] Grower errors do not crash main service process.
- [ ] grower 异常不会杀死主服务进程。

- [ ] `/grower/start` and `/grower/stop` work.
- [ ] `/grower/start` 与 `/grower/stop` 可用。

---

## E. Data safety
## E. 数据安全

- [ ] Journal raw entries are readable and immutable in intent.
- [ ] journal 原始条目可读且不应被业务改写。

- [ ] `wipe_derived` clears derived layers while preserving narrative/history.
- [ ] `wipe_derived` 清空派生层并保留 narrative/history。

- [ ] `reset_digestion` re-queues raw material for reprocessing.
- [ ] `reset_digestion` 能把生料重新排队重煮。

---

## F. Regression test suite
## F. 回归测试

- [ ] `python tests/test_growth.py`
- [ ] `python tests/test_growth.py`
- [ ] `python tests/test_network.py`
- [ ] `python tests/test_network.py`
- [ ] `python tests/test_digest.py`
- [ ] `python tests/test_digest.py`
- [ ] `python tests/test_store.py`
- [ ] `python tests/test_store.py`
- [ ] `python tests/test_context.py`
- [ ] `python tests/test_context.py`
- [ ] `python tests/test_server.py`
- [ ] `python tests/test_server.py`
- [ ] `python tests/test_integration.py`
- [ ] `python tests/test_integration.py`

Keep one full stdout snapshot as baseline before release.
建议保留一份全量 stdout 作为上线前基线。