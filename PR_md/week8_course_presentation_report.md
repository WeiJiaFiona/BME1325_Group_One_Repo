# Week 8 课程汇报文档：ED-MAS Memory v1（A/B 合并版）

项目根目录（Week 8 合并系统）：
- `/home/jiawei2022/BME1325/week8/merge`

本周总目标（来自 proposal）：
- 参考 `/home/jiawei2022/BME1325/week8/merge/PR_md/week8_proposal.md`，在合并后的急诊多智能体系统上实现 **Memory v1**：
  - continuity（跨角色连续性）
  - handoff quality（交接完整性）
  - replay/audit（可回放、可审计）
  - repeated-question reduction（降低重复提问）
  - memory ON/OFF ablation（可量化对照）

---

## 1. 我们参考了 Group4 的什么（数据/数据库格式）

参考仓库：
- `/home/jiawei2022/BME1325/week8/reference/BME_1325_Group4_repo`

参考重点不是直接搬运行代码，而是借鉴 **数据层架构模式**（episode anchor + append-only events + current materialized state + snapshots + audit + API boundary）。

### 1.1 Group4 的数据表/事件格式（摘取要点）
来自：`system/backend/数据规范/数据类型.md`

- `patients / beds / admissions`：把一次住院/episode 用 `admission_id` 作为锚点。
- `events`：append-only 事件流，字段包含：
  - `event_type`（vital_sign / lab / intervention / agent_output）
  - `timestamp`、`priority`、`payload`（JSON）
- `patient_state_current`：当前状态物化视图（可由 events 重建）。
- `patient_state_snapshots`：定期快照。
- `audit_logs`：操作审计。

我们在 ED 场景下做的迁移：
- 将 Group4 的 `admission_id` 思想迁移为 ED 的 `run_id + encounter_id`（episode anchor）。
- 将 `events` 迁移为 `MemoryItem`（append-only event bus）。
- 将 `patient_state_current` 迁移为 `CurrentEncounterSummary`（current materialized state）。
- 将 `patient_state_snapshots` 思想迁移为 `HandoffMemorySnapshot`（交接快照）。
- 增加 audit trail，保证写入与检索可追踪。

---

## 2. Week 8 我们实现了哪些目标（对照 proposal）

### 2.1 shared-but-mode-isolated memory substrate
- 代码位置：`/home/jiawei2022/BME1325/week8/merge/app_core/memory/`
- 关键点：
  - auto 和 user 共用同一套 schema/存储/检索/回放接口
  - 但每条记录都带 `run_id + mode + encounter_id + patient_id`，避免跨模式混写

### 2.2 Append-only events + 可重建 summary + handoff snapshot
- `MemoryItem`：原始事实事件（append-only）
- `CurrentEncounterSummary`：当前状态视图（可重建，不是事实源）
- `HandoffMemorySnapshot`：面向接收方的交接快照（requested/completed 两阶段）

### 2.3 Bounded retrieval（受控检索）
- `MemoryQuery`：限制 top_k、age window、checkpoint
- 不做 always-on retrieval（避免把 memory 变成“每轮都检索”的隐性 planner）

### 2.4 Replay / Export / Audit
- 存储后端：JSONL events + JSON summaries/snapshots + JSONL audits
- 支持 replay 导出（events + summaries + snapshots + audits）
- 增加导出脚本，方便课堂演示：
  - `/home/jiawei2022/BME1325/week8/merge/scripts/export_memory_replay.py`

### 2.5 User-mode hooks（端到端连通）
在 user mode（calling nurse → triage → doctor → bedside nurse）流程中写入关键 event types：
- `encounter_started`
- `calling_nurse_called`
- `vitals_measured`
- `triage_completed`
- `doctor_assessment_started`
- `doctor_assessment_checkpoint`
- `disposition_decided`
- `handoff_requested`
- `handoff_completed`
- `encounter_closed`

并且保持 Week 8 明确边界不变：
- 不改 doctor planner ownership
- 不改 `next_slot` ownership
- 不改 safety floor / disposition ownership
- 不改 `EDSIM_MODE`（后端启动模式唯一真源）

### 2.6 Memory ON/OFF Ablation
- 主开关：`MEMORY_V1_ENABLED=0/1`
- 目标：在不改变 hard-rule 决策的情况下，比较 memory OFF vs ON

---

## 3. 我们做了什么测试，如何测试

### 3.1 A-side substrate 单元测试（schema/storage/service/retrieval）
命令：
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests/backend/test_memory_schema.py \
         tests/backend/test_memory_storage.py \
         tests/backend/test_memory_service.py \
         tests/backend/test_memory_retrieval.py
```
结果：
- `12 passed`

覆盖点：
- schema 校验（字段类型、event_type/top_k bounds）
- JSONL/JSON 存储 round-trip
- bounded retrieval 的 run/encounter 隔离与 top_k/age window
- replay export 包含 events/summaries/snapshots/audits

### 3.2 Week8 集成测试（tests_week8）
命令：
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_week8
```
结果：
- `9 passed, 1 skipped`
- skipped 项为 auto-mode integration skeleton（按本周 scope 暂缓）

覆盖点：
- user-mode end-to-end 产生 replay 并可导出
- ON/OFF ablation：OFF 不产出有效 events；ON 产出 events/summaries/snapshots
- fail-open：强制 memory service 抛异常，user 临床流程仍能继续（不崩溃）

### 3.3 user-mode 回归测试
命令：
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_user
```
结果：
- `62 passed`（存在 warnings，不影响功能）

覆盖点：
- calling nurse + pending_messages + phase auto-progression
- doctor 单问/防循环
- triage pain-score 不再总是 CTAS 3

### 3.4 手工 artifact 检查（demo/报告准备）
Memory enabled 且指定 root 后，检查以下结构：
- `events.jsonl`
- `audit.jsonl`
- `current/<mode>/<run_id>/<encounter_id>.json`
- `snapshots/<mode>/<run_id>/<encounter_id>/<snapshot_id>.json`

---

## 4. 当前存在的问题（existing problems）

1. **auto-mode memory 接入仍 deferred**
- 目前 user-mode 完整接入并验证；auto-mode 仅保留 skeleton。
- 原因：reverie backend 的 import path 与 app_core 运行域隔离，若强行做 auto hook 需要额外 shim，属于更高风险改动。

2. **并发写入的文件锁/一致性风险**（未来需要处理）
- 当前 JSONL 后端若 auto/user 同时跑且指向同一 `MEMORY_V1_ROOT`，可能出现写入竞争。
- 现阶段建议：auto/user 分离 root（例如 `.../memory_auto` vs `.../memory_user`）。

3. **检索与临床“减少重复问”效果目前主要依赖 hooks 与 summary，而不是更强的语义检索**
- Week 8 明确不做 embedding/vector retrieval；因此“重复问降低”的收益有限且依赖后续策略。

4. **审计与安全还不完整**
- 已有 audit trail 结构，但“安全/伦理/PHI 处理”未系统化实现（留到 Week 9）。

---

## 5. 下一步改进计划（Week 9: Safety/Ethics + Recovery）

### Target
- Risk control is testable and auditable.

### Implementation Plan
1. High-risk advice block rules
- 在 LLM 输出层增加危险建议拦截（例如用规则或 policy gate 拦截剂量、危险操作指导）。

2. PHI redaction and audit trail
- 在 memory 写入前，对 `content/structured_facts` 做 PHI 脱敏（姓名、电话、身份证、地址等）。
- audit 记录：何时触发 redaction、被替换字段类型。

3. Fallback-to-rule mode during model/tool timeout
- LLM/RAG 超时或异常时，系统退化到规则驱动（不崩溃、不乱出院/不乱分流）。
- 保持 ownership：hard-rule 决策优先。

### Test Plan
1. Dangerous dosage suggestion injection
- 输入诱导医生给出危险剂量/处方，验证被拦截并记录审计。

2. Sensitive info leakage attempt
- 用户尝试输入/诱导输出 PHI，验证 redaction 生效，memory 中不落敏感原文。

3. Timeout during active encounter
- 模拟 LLM/RAG 超时，验证 workflow 不坍塌，仍能完成 disposition/handoff。

### Robustness Evidence
- Safe degradation without workflow collapse.

### Milestone
- Safety test suite and audit logs pass review.

---

## 6. 下周（Week 9）的具体目标清单

1. 增加 `tests_week9_safety/`（或在 `tests_week8` 扩展）覆盖：危险建议、PHI、超时退化。
2. 在 user-mode doctor 输出链路加入安全过滤与审计记录（不改 hard-rule ownership）。
3. 在 memory 写入前增加 redaction pipeline（并记录 audit）。
4. 增加“超时/异常退回 rule-mode”的 deterministic 行为测试。
5. （可选）若时间充裕，再做 1 个最小 auto-mode memory hook（boarding_timeout）以便展示跨模式能力。
