# loam 集成上线前检查清单

## A. 基础运行

- [ ] `python -m loam --help` 正常输出
- [ ] `python -m loam stats --character demo --home <dir>` 可读到空库状态
- [ ] `python -m loam init-secrets --secrets-home ~/.loam` 生成模板

## B. 端到端链路（无 key）

- [ ] 运行 `python /home/loam/e2e_smoke.py`，看到 `✅ smoke ok`
- [ ] ingest 成功后 `pending > 0`
- [ ] 无 key 时 `digest_once` 返回错误且 `pending` 不减少（生料不丢）

## C. 端到端链路（有 key）

- [ ] `~/.loam/secrets.json` 已填 `api_key/base_url/model`
- [ ] `model` 使用你指定的 **flash** 模型 ID
- [ ] ingest 后 `digest_once` 出现 `新事件 > 0`
- [ ] `/context` 返回 `recalled` 非空，且文本包含“被想起的经历”
- [ ] `/stats` 中 `memory.事件` 随对话增长

### C1. “是否是长出来”专项验证（真实模型）

- [ ] 设置 `LOAM_API_KEY` 与 `LOAM_MODEL=<flash模型ID>`
- [ ] 运行 `python /home/loam/probe_growth_real_brain.py`
- [ ] 观察输出表格中 `direct/soothe` 强度随阶段变化（先A后B）
- [ ] 若变化过小，增加样本到 20~30 周期再测

## D. 后台成长线程

- [ ] `auto_start_grower=true` 时，空闲后会自动消化
- [ ] `grower` 异常不会杀死进程（`last_error` 可见但服务仍活）
- [ ] 可以通过 `/grower/start` 与 `/grower/stop` 控制

## E. 数据安全

- [ ] journal 原始条目可读，且不被改写
- [ ] wipe_derived 后，events/traits/network 清空，但 narrative/history 保留
- [ ] reset_digestion 后，生料重新排队可重煮

## F. 回归测试

- [ ] `python tests/test_growth.py`
- [ ] `python tests/test_network.py`
- [ ] `python tests/test_digest.py`
- [ ] `python tests/test_store.py`
- [ ] `python tests/test_context.py`
- [ ] `python tests/test_server.py`
- [ ] `python tests/test_integration.py`

> 建议：上线前跑一轮全测试，并保存一份 stdout 作为回归基线。