# Auto Mode Week13 Implementation：Composite Failure Rate 与资源瓶颈阈值搜索

> 面向：BME1325 模拟医院 / Auto Mode / Week13 Priority Task  
> 输出文件：`implementation.md`  
> 核心定位：从“资源真实性”推进到“后果量化 + 负荷阈值搜索 + 瓶颈诊断”  
> 重要边界：本文中的 `failure_rate` 是 **project-defined composite operational metric**，不是现实医院官方统一质量指标。

---

## 0. 总目标

本轮 Week13 的总目标不是继续随意增加资源参数，也不是重写 ICU / 病房 / 前端 UI，而是建立一套可解释、可测试、可复现的资源压力测试框架：

> 先基于真实 ED 场景定义不同等级医院的医生/护士配置与标准医患比、护患比；然后固定医生和护士数量，把患者数量作为主要变量，观察患者压力逐步增加时 `failure_rate` 如何变化，并用 coarse-to-fine / threshold-search 方法找到系统从“可承受”到“失效”的临界负荷。

最终希望得到的结果包括：

1. 不同医院等级下的 `doctor_count / nurse_count / normal_patient_count`。
2. 患者负荷从 normal 增加到 overload 时，`failure_rate` 如何变化。
3. `failure_rate` 第一次超过阈值，例如 0.1，时的 `threshold_load_factor`。
4. 主导 failure 的原因：CTAS 等待违约、LWBS/walkout、boarding timeout、ED LOS 超阈值、queue overflow，还是严重创伤救治延误。
5. 系统瓶颈归因：医生、护士、lab/imaging、boarding 出口堵塞，还是下游转运接口。

---

# 第一部分：先验知识

## 1.1 真实 ED 运营指标

真实急诊系统的质量与运营评价通常不是一个单一指标，而是一组指标共同构成。对于本项目，这些指标的作用不是“原样复制现实医院”，而是为 Auto Mode 的仿真评价层提供结构化依据。

### 1.1.1 真实 ED 指标与系统迁移表

| 真实 ED 指标 | 现实含义 | 可获得的具体信息 / 数值 | 在系统中的迁移方式 | 证据状态 |
|---|---|---|---|---|
| 急诊科医患比 | 急诊医生数量相对于急诊患者负荷的比例 | 公开资料支持其作为急诊质控指标；未检索到全国统一硬性数值 | 映射为 `doctor_count`、`standard_patients_per_doctor`、`doctor_patient_ratio` | 指标定义可靠；数值采用工程默认 |
| 急诊科护患比 | 急诊护士数量相对于急诊患者负荷的比例 | 公开资料支持其作为急诊质控指标；未检索到全国统一硬性数值 | 映射为 `nurse_count`、`standard_patients_per_nurse`、`nurse_patient_ratio` | 指标定义可靠；数值采用工程默认 |
| 抢救室滞留时间 | 高危患者在抢救室停留过久反映资源拥堵与出口阻塞 | 作为急诊质控指标出现；具体医院分布通常不公开 | 后续映射为 `resus_dwell_time_minutes_p50/p90` | Phase 2/3 指标 |
| 分级分诊执行率 | 反映患者是否按病情等级进入相应诊疗优先级 | 中国急诊常见 4 级语义；当前系统内核使用 CTAS 1–5 | 映射为 `CTAS`、`ctas_compliance_rate`、`ctas_violations_by_level` | 立即可落地 |
| 严重创伤就诊到手术时间 | 严重创伤关键救治是否延误 | 作为急诊质控指标出现；当前系统未完整建模创伤手术事件 | 映射为 `severe_trauma_time_to_surgery_violation` | 先做 helper/schema |
| admission-to-ward / boarding waiting time | 医生决定住院到患者离开 ED 去病房/ICU 的等待时间 | 新加坡卫生部等公开运营指标使用该定义；文献中 ED boarding 指已决定住院但仍滞留 ED | 映射为 `boarding_wait_minutes`、`boarding_timeout_event`、`boarder_count` | 当前系统已有基础 |
| CTAS 目标等待时间 | 不同急诊分级下应在多久内被医生评估 | CTAS 1=0 min, CTAS 2=15 min, CTAS 3=30 min, CTAS 4=60 min, CTAS 5=120 min | 映射为 `ctas_target_wait_minutes`、`ctas_target_wait_violation` | 立即可落地 |

### 1.1.2 可直接写入系统的 CTAS 默认目标

```json
{
  "ctas_target_wait_minutes": {
    "1": 0,
    "2": 15,
    "3": 30,
    "4": 60,
    "5": 120
  }
}
```

解释：

- CTAS 1：立即处理。
- CTAS 2：15 分钟内。
- CTAS 3：30 分钟内。
- CTAS 4：60 分钟内。
- CTAS 5：120 分钟内。

这些数值适合直接作为系统 `ctas_target_wait_minutes` 默认参数。

### 1.1.3 可作为医院规模锚点的公开资料

| 医院 / 场景 | 公开数据 | 适合如何使用 |
|---|---|---|
| 华山医院急诊中心 | 上传资料整理中记录：年诊疗病人 62 万余人次、床位 360 余张 | 可作为 `large_tertiary_ed` 的超大型急诊量级锚点 |
| 北京协和医院急诊科 | 上传资料整理中记录：年均急诊患者 20 余万人次，日均 600–700 人次 | 可作为大型三甲急诊 baseline 量级锚点 |
| 上海第九人民医院 | 上传资料整理中记录：存在 4.58 million emergency outpatient visits 的规模描述，但口径更像门急诊合并量 | 只能作为超大体量背景，不直接作为 ED arrival/day |
| 瑞金医院 | 上传资料整理中标注：未找到稳定可用的独立 ED throughput | 不应硬填数据，应标注公开资料缺口 |
| 县医院 / 基层医院 | 可从县医院医疗服务能力标准、县域医院建设文件获得政策背景，但急诊班次 staffing 数字通常不公开 | 作为 `small_county_ed` 的政策场景，数值采用工程默认 |

### 1.1.4 重要边界

本文后续表格中给出的医患比、护患比是：

```text
scenario-calibrated engineering defaults
```

不是：

```text
国家官方统一标准
```

原因是：公开资料可以支持“医患比/护患比是重要急诊运营指标”，但并不稳定提供全国统一硬性数值。因此，本文先使用工程默认值完成可复现实验框架，后续可由 `docs/ed_staffing_evidence_table.md` 替换为真实医院证据。

---

## 1.2 当前系统已经具备的工程参数

根据 Week12 Auto Mode 资源真实性核验，当前系统并不是从零开始。已有工程基础如下：

| 参数 / 事件 | 当前系统含义 | Week13 中的作用 |
|---|---|---|
| `arrival_profile_mode` | 控制患者背景到达模式，已有 `normal / surge / burst` | 作为 background arrival profile |
| `patient_rate_modifier` | 调节基础患者到达率 | 可用于 stress multiplier |
| `lab_capacity` | lab 同时服务容量 | 资源瓶颈测试中的固定资源 |
| `imaging_capacity` | imaging 同时服务容量 | 资源瓶颈测试中的固定资源 |
| `lab_turnaround_minutes` | lab 周转时间 | testing TAT 参数 |
| `imaging_turnaround_minutes` | imaging 周转时间 | testing TAT 参数 |
| `boarding_timeout_minutes` | boarding 超时阈值 | 直接进入 failure reason |
| `boarding_timeout_event` | 患者达到 boarding timeout 后记录的事件 | 直接进入 `boarding_timeout` failure reason |
| `CTAS` | 当前系统已有患者分级 | 用于 `ctas_target_wait_violation` 与 priority queue |

当前缺失的是：

1. `failed_patients`
2. `failure_rate`
3. `failure_reasons_by_patient`
4. `ctas_target_wait_violation_count`
5. `preload_sensitivity_report`
6. `threshold_search_report`

因此 Week13 的核心不是重写已有流程，而是在现有基础上新增：

```text
failure metrics layer
+ hospital scenario config layer
+ preload experiment layer
+ threshold search analysis layer
```

---

# 第二部分：真实参数 + 医疗场景的固定信息

## 2.1 医院场景分类原则

建议将 ED 场景分为 3 类主实验场景 + 1 类边界演示场景：

| 场景 ID | 中文名称 | 现实语义 | 是否主实验 |
|---|---|---|---|
| `large_tertiary_ed` | 大型三甲 / 区域中心急诊 | 高日均到诊量、急诊中心规模大、专科支持多 | 是 |
| `medium_city_ed` | 城市中型综合医院急诊 | 资源中等，作为城市 baseline | 是 |
| `small_county_ed` | 小县城 / 基层医院急诊 | 医护数量少，抗瞬时冲击能力弱 | 是 |
| `night_low_resource_ed` | 夜间低资源值班场景 | 极端低资源边界，不代表正式医院等级 | 否，仅 stress demo |

---

## 2.2 normal_patient_count 计算方式

每类医院均定义：

```text
doctor_supported_patients = doctor_count × standard_patients_per_doctor
nurse_supported_patients  = nurse_count × standard_patients_per_nurse

normal_patient_count = min(
    doctor_supported_patients,
    nurse_supported_patients
)
```

取 `min` 的原因是：急诊是链条系统，医生和护士任一侧成为短板，都会限制系统的 normal capacity。

---

## 2.3 医院场景默认配置表

> 注意：以下数值为 Week13 仿真实验工程默认值，等待真实证据表进一步替换，不是官方统一标准。

| 场景 ID | 医院类型 | `doctor_count` | `nurse_count` | 仿真标准医患比 | 仿真标准护患比 | `normal_patient_count` | 证据状态 |
|---|---|---:|---:|---:|---:|---:|---|
| `large_tertiary_ed` | 大型三甲 / 区域中心急诊 | 8 | 16 | 1:8 | 1:4 | 64 | 工程默认；由华山/协和等大型急诊量级作为背景锚点 |
| `medium_city_ed` | 城市中型综合医院急诊 | 4 | 8 | 1:7 | 1:3.5 | 28 | 工程默认；作为中等资源 baseline |
| `small_county_ed` | 小县城 / 基层医院急诊 | 2 | 4 | 1:6 | 1:3 | 12 | 工程默认；用于基层/县域场景冲击测试 |
| `night_low_resource_ed` | 夜间低资源边界场景 | 1 | 2 | 1:5 | 1:2.5 | 5 | 极端 demo；不作为正式医院等级 |

---

## 2.4 负荷等级定义

| 负荷等级 | 计算方式 | 含义 |
|---|---:|---|
| `normal` | `1.0 × normal_patient_count` | 标准医患比/护患比下的正常患者负荷 |
| `mild_stress` | `1.2 × normal_patient_count` | 轻度压力 |
| `stress` | `1.5 × normal_patient_count` | 明显压力 |
| `overload` | `2.0 × normal_patient_count` | 超载压力 |
| `extreme` | `2.5–3.0 × normal_patient_count` | 边界测试 |

---

## 2.5 建议新增配置文件

### 2.5.1 `configs/hospital_level_profiles.json`

```json
{
  "large_tertiary_ed": {
    "scenario_status": "engineering_default_pending_evidence_fill",
    "doctor_count": 8,
    "nurse_count": 16,
    "standard_patients_per_doctor": 8,
    "standard_patients_per_nurse": 4,
    "normal_patient_count": 64,
    "load_factors": [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
  },
  "medium_city_ed": {
    "scenario_status": "engineering_default_pending_evidence_fill",
    "doctor_count": 4,
    "nurse_count": 8,
    "standard_patients_per_doctor": 7,
    "standard_patients_per_nurse": 3.5,
    "normal_patient_count": 28,
    "load_factors": [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
  },
  "small_county_ed": {
    "scenario_status": "engineering_default_pending_evidence_fill",
    "doctor_count": 2,
    "nurse_count": 4,
    "standard_patients_per_doctor": 6,
    "standard_patients_per_nurse": 3,
    "normal_patient_count": 12,
    "load_factors": [1.0, 1.5, 2.0, 2.5, 3.0]
  },
  "night_low_resource_ed": {
    "scenario_status": "extreme_demo",
    "doctor_count": 1,
    "nurse_count": 2,
    "standard_patients_per_doctor": 5,
    "standard_patients_per_nurse": 2.5,
    "normal_patient_count": 5,
    "load_factors": [1.0, 2.0, 3.0]
  }
}
```

### 2.5.2 验收标准

该配置文件通过验收必须满足：

1. 至少定义 3 类医院场景：large / medium / small。
2. 每类都有 `doctor_count`、`nurse_count`、标准医患比、标准护患比。
3. 每类都能计算 `normal_patient_count`。
4. 明确标注哪些是真实证据，哪些是 engineering default。
5. 不允许把工程默认值写成官方统一标准。

---

# 第三部分：failure_rate 定义 + implementation 说明

## 3.1 failure_rate 正式定义

名称：

```text
simulation-defined composite operational failure rate
```

中文：

```text
仿真定义的复合运营失败率
```

公式：

```text
failed_patients = set(patient_id)

如果某患者触发任一 failure reason:
    failed_patients.add(patient_id)

failure_rate = len(failed_patients) / total_arrived_patients
```

关键原则：

1. 一个患者可以触发多个 failure reason。
2. 同一个患者在 `failed_patients_count` 中只算一次。
3. 同一个患者同一个 failure reason 不重复记录。
4. `failed_at_step` 只记录第一次失败 step。
5. 分母 `total_arrived_patients` 是累计到达患者数，不是当前在院患者数。
6. 若分母为 0，则 `failure_rate=0.0`，`system_failed=False`。

---

## 3.2 Failure reasons

| failure reason | 定义 | MVP 是否启用 | 注意事项 |
|---|---|---|---|
| `ctas_target_wait_violation` | 患者完成 triage 后，未在 CTAS 目标时间内获得首次医生评估 | 是 | 需要 `triage_completed_at` 和 `first_doctor_contact_at` |
| `walkout_lwbs` | 患者未完成诊疗闭环即离开 | 是 | 若当前系统没有真实 walkout 行为，先做 schema/helper |
| `boarding_timeout` | 已决定住院但在 ED boarding 超过阈值 | 是 | 当前系统已有 `boarding_timeout_event` |
| `queue_overflow_exposure` | 患者在超阈值队列中暴露超过指定时长 | 是 | 可先做 helper 和 fake test |
| `ed_los_over_threshold` | ED 总停留时间超过阈值 | 是 | 需要 `ed_arrival_at` 和 `ed_exit_at` |
| `severe_trauma_time_to_surgery_violation` | 严重创伤未在目标时间内进入关键救治节点 | Better/Full | 不要伪造 trauma outcome |
| `critical_outcome_event` | 明确严重结局事件 | 仅 explicit event | 不允许随机生成死亡率 |

---

## 3.3 默认参数

```python
DEFAULT_FAILURE_THRESHOLD = 0.1
DEFAULT_SYSTEM_FAILED_COMPARATOR = "gt"

DEFAULT_CTAS_TARGET_WAIT_MINUTES = {
    "1": 0,
    "2": 15,
    "3": 30,
    "4": 60,
    "5": 120,
}

DEFAULT_ED_LOS_FAILURE_THRESHOLD_MINUTES = 720
DEFAULT_SEVERE_TRAUMA_SURGERY_TARGET_MINUTES = 90

DEFAULT_DOCTOR_QUEUE_OVERFLOW_THRESHOLD = 20
DEFAULT_LAB_QUEUE_OVERFLOW_THRESHOLD = 15
DEFAULT_IMAGING_QUEUE_OVERFLOW_THRESHOLD = 10
DEFAULT_OVERFLOW_EXPOSURE_MINUTES = 30
```

`system_failed` 判定：

```python
if comparator == "gt":
    system_failed = failure_rate > failure_threshold
elif comparator == "gte":
    system_failed = failure_rate >= failure_threshold
```

边界例子：

```text
300 patients, 30 failed:
failure_rate = 0.1

comparator = "gt"  -> system_failed = False
comparator = "gte" -> system_failed = True
```

---

# 第四部分：Implementation Phases

## Phase 0：Scope audit，不改代码

### 目标

确认当前代码已经有什么，缺什么，避免 Codex 重复造轮子或误改状态机。

### 需要检查

1. `reverie/backend_server/failure_metrics.py` 是否已存在。
2. `reverie.py::_write_sim_status` 当前输出哪些 `resources` 字段。
3. `patient.py` 中 `boarding_timeout_event` 如何记录。
4. `analysis/compute_metrics.py` 当前输出哪些 analysis 文件。
5. `scripts/verify_step_contract.py` 当前检查哪些内容。
6. 是否已有 `preload_waiting_room_patients` 或类似预装载入口。

### Return

```text
docs/week13_scope_audit.md
```

### 验收标准

1. 列出已有字段。
2. 列出缺失字段。
3. 列出本轮要改的文件。
4. 明确本轮不做完整 ICU/病房仿真。
5. 明确不修改 arrival/testing/patient state/movement schema。

---

## Phase 1：Hospital profile 与 preload 配置

### 目标

把不同医院等级和 preload 测试矩阵配置化，让后续实验不是手动调参数。

### 修改 / 新增文件

```text
configs/hospital_level_profiles.json
configs/preload_sensitivity_matrix.csv
configs/single_time_preload_shock_matrix.csv
docs/ed_staffing_evidence_table.md
```

### Return

1. `hospital_level_profiles.json`
2. `preload_sensitivity_matrix.csv`
3. `single_time_preload_shock_matrix.csv`
4. `ed_staffing_evidence_table.md`

### 验收标准

1. 至少 3 个 profile：`large_tertiary_ed`、`medium_city_ed`、`small_county_ed`。
2. 每个 profile 都有医生数、护士数、医患比、护患比。
3. `normal_patient_count` 可复算，且与配置一致。
4. 所有默认医患比/护患比都标注为 engineering default。
5. 测试矩阵中每个 scenario 都能计算出 `preload_patient_count = round(normal_patient_count × load_factor)`。

---

## Phase 2：failure_metrics.py 纯函数实现

### 目标

先实现 failure_rate 的数学定义，不接入真实 Auto run。

### 修改 / 新增文件

```text
reverie/backend_server/failure_metrics.py
tests/backend/test_failure_metrics.py
```

### 核心函数

```python
def collect_failure_metrics(
    personas,
    maze,
    data_collection,
    meta,
    curr_time,
    curr_step
):
    ...
```

### 必须返回

```python
{
    "total_arrived_patients": int,
    "failed_patients_count": int,
    "failure_rate": float,
    "system_failed": bool,
    "failure_threshold": float,
    "system_failed_comparator": str,
    "failure_reason_counts": dict,
    "failure_reasons_by_patient": dict,
    "failed_at_step": dict,
    "lwbs_count": int,
    "boarding_timeout_count": int,
    "ctas_target_wait_violation_count": int,
    "ed_los_over_threshold_count": int,
    "queue_overflow_exposure_count": int,
    "severe_trauma_time_to_surgery_violation_count": int,
    "critical_outcome_event_count": int
}
```

### Return

1. `failure_metrics.py`
2. `tests/backend/test_failure_metrics.py`

### 验收标准

必须通过以下测试：

1. `test_empty_failure_metrics`
2. `test_no_failed_patients`
3. `test_one_failed_patient`
4. `test_duplicate_reason_not_repeated`
5. `test_multiple_reasons_count_one_patient`
6. `test_failed_at_step_first_only`
7. `test_walkout_scratch_counted`
8. `test_lwbs_event_counted`
9. `test_boarding_timeout_event_counted`
10. `test_boarding_timeout_scratch_counted`
11. `test_ctas2_20min_violation`
12. `test_ctas2_10min_compliant`
13. `test_ctas5_130min_violation`
14. `test_ctas_compliance_rate`
15. `test_ed_los_over_threshold`
16. `test_queue_overflow_exposure`
17. `test_queue_short_spike_not_failure`
18. `test_severe_trauma_delayed_surgery_violation`
19. `test_severe_trauma_timely_surgery_success`
20. `test_no_mortality_not_fabricated`
21. `test_failure_rate_gt_equal_boundary_false`
22. `test_failure_rate_gte_boundary_true`
23. `test_failure_rate_gt_above_threshold_true`
24. `test_invalid_comparator_fallback`

---

## Phase 3：接入 sim_status / dashboard API / analysis

### 目标

让真实 Auto run 能输出 failure metrics。

### 修改文件

```text
reverie/backend_server/reverie.py
environment/frontend_server/translator/views.py
analysis/compute_metrics.py
scripts/verify_step_contract.py
environment/frontend_server/templates/home/live_dashboard.html
```

### 新增 sim_status 字段

```json
{
  "resources": {
    "total_arrived_patients": 120,
    "failed_patients_count": 14,
    "failure_rate": 0.1167,
    "system_failed": true,
    "failure_threshold": 0.1,
    "system_failed_comparator": "gt",
    "failure_reason_counts": {
      "ctas_target_wait_violation": 8,
      "boarding_timeout": 4,
      "ed_los_over_threshold": 2
    }
  },
  "system_health": {
    "failed": true,
    "failed_reason": "failure_rate_exceeded_threshold",
    "failure_rate": 0.1167,
    "failed_at_step": 87
  }
}
```

### 新增 analysis 输出

```text
analysis/failure_report.json
```

必须包含：

```json
{
  "arrivals_total": 120,
  "failed_patients_count": 14,
  "failure_rate": 0.1167,
  "system_failed": true,
  "failure_reasons_by_patient": {
    "patient_023": [
      "boarding_timeout",
      "ed_los_over_threshold"
    ]
  },
  "failed_at_step": {
    "patient_023": 35
  }
}
```

### Return

1. `sim_status.json` 中出现 failure 字段。
2. `/api/live_dashboard/` 能返回 failure metrics。
3. `analysis/failure_report.json` 能生成。
4. `verify_step_contract.py` 支持 failure metrics schema 检查。

### 验收标准

1. `sim_status.json.resources.failure_rate` 存在。
2. `sim_status.json.resources.failure_reason_counts` 存在。
3. `sim_status.json.system_health.failed` 存在。
4. `analysis/failure_report.json` 存在。
5. dashboard API 缺字段时不报 500。
6. verify 普通模式 warning-only。
7. verify strict 模式缺字段 hard fail。
8. 不改变原有 arrival/testing/patient state/movement 行为。

---

## Phase 4：Preload sensitivity runner

### 目标

实现“固定医生护士，改变患者数量”的实验执行器。

### 修改 / 新增文件

```text
scripts/run_preload_sensitivity.py
analysis/preload_sensitivity_report.json
tests/backend/test_preload_threshold_search.py
```

### 输入

```text
configs/hospital_level_profiles.json
configs/preload_sensitivity_matrix.csv
```

### 输出指标

| 指标 | 含义 |
|---|---|
| `failure_rate` | 核心结果 |
| `failed_patients_count` | 失败患者数 |
| `dominant_failure_reason` | 主导失败原因 |
| `peak_doctor_queue` | 医生瓶颈 |
| `peak_lab_queue` | lab 瓶颈 |
| `peak_imaging_queue` | imaging 瓶颈 |
| `boarder_peak` | boarding 出口堵塞 |
| `system_failed` | 是否超过阈值 |

### Return

```text
analysis/preload_sensitivity_report.json
```

### 验收标准

1. large / medium / small 三类 profile 都能生成测试场景。
2. 每类 profile 至少包含 5 个 `load_factor`。
3. 每个 scenario 都输出 `failure_rate`。
4. report 中存在 `load_factor -> failure_rate` 的结果表。
5. 能输出 `dominant_failure_reason`。
6. 不依赖前端 UI。
7. 不破坏原有 Auto Mode run。

---

## Phase 5：Small hospital single-time preload shock

### 目标

模拟小县城/基层医院在同一时间点突然接入一批患者时，系统是否能够恢复。

### 修改 / 新增文件

```text
scripts/run_small_hospital_shock.py
analysis/small_hospital_shock_report.json
```

### 默认场景

```yaml
scenario_id: small_county_single_time_preload_shock
hospital_profile: small_county_ed
doctor_count: 2
nurse_count: 4
normal_patient_count: 12
load_factor: 2.0
preload_patient_count: 24
arrival_profile_mode: normal
background_arrival_enabled: false
run_steps: 1000
random_seed: 42
```

### Return

```text
analysis/small_hospital_shock_report.json
```

### 验收标准

1. small_county_ed 能以 `2.0x` 和 `3.0x` normal load 跑通。
2. 输出 `failure_rate`。
3. 输出 `time_to_recovery`。
4. 输出 `dominant_failure_reason`。
5. 输出 `peak_queue_step`。
6. 能判断小医院是否进入 `system_failed=True`。

---

## Phase 6：Coarse-to-fine threshold search

### 目标

自动寻找 `failure_rate` 刚刚超过阈值的患者负荷。

### 修改 / 新增文件

```text
scripts/run_failure_threshold_search.py
configs/failure_rate_threshold_search.yaml
analysis/threshold_search_report.json
```

### 算法流程

```text
1. coarse sweep:
   load_factor = [1.0, 1.2, 1.5, 2.0, 2.5, 3.0]

2. 找到:
   last_safe = 最后一个 failure_rate <= threshold 的点
   first_fail = 第一个 failure_rate > threshold 的点

3. fine sweep:
   在 [last_safe, first_fail] 之间以 0.05 或 0.1 为步长继续搜索

4. 每个点跑多个 seed

5. 取 median failure_rate

6. 输出 threshold_load_factor
```

### Return

```text
analysis/threshold_search_report.json
```

必须包含：

```json
{
  "hospital_profile": "medium_city_ed",
  "failure_threshold": 0.1,
  "system_failed_comparator": "gt",
  "threshold_load_factor": 1.55,
  "threshold_preload_patient_count": 43,
  "median_failure_rate_at_threshold": 0.112,
  "dominant_failure_reason": "ctas_target_wait_violation"
}
```

### 验收标准

1. 能自动跑 coarse sweep。
2. 能识别 `last_safe / first_fail`。
3. 能进入 fine sweep。
4. 每个点支持多 seed。
5. 输出 `threshold_load_factor`。
6. 输出 `threshold_preload_patient_count`。
7. 输出主导 failure reason。
8. 输出可解释结论。

---

## Phase 7：Downstream / ICU interface stub

### 目标

只做未来接口文档和轻量 schema，不做完整 ICU 仿真。

### 新增文件

```text
docs/downstream_interface_stub.md
```

### 未来字段

```text
downstream_destination = ward | ICU | OR | discharge
decision_to_admit_at
downstream_capacity
downstream_queue_len
ed_exit_at
boarding_wait_minutes
transfer_failed_reason
```

### 本轮边界

本轮 Week13 仍使用 `boarding_timeout` 代表下游出口堵塞，不接入完整 ICU runtime。

### 验收标准

1. 文档说明未来如何接 ICU / ward / OR。
2. 不改 patient state machine。
3. 不新增 ICU capacity runtime 行为。
4. 不影响本轮 failure_rate 主实现。

---

# 第五部分：Codex 执行指令摘要

请 Codex 按以下顺序执行：

```text
Phase 0: scope audit
Phase 1: hospital profiles + preload configs
Phase 2: failure_metrics.py pure helper
Phase 3: sim_status / dashboard / analysis integration
Phase 4: preload sensitivity runner
Phase 5: small hospital shock runner
Phase 6: threshold search runner
Phase 7: downstream interface stub
```

每个 Phase 完成后必须返回：

```text
Summary
Files Changed
Return Artifacts
Tests Run
Acceptance Result
Behavior Not Changed
Known Limitations
```

---

# 第六部分：总验收命令

建议最终执行：

```bash
python -m pytest tests/backend/test_failure_metrics.py -q
python -m pytest tests/frontend/test_views.py -q
python -m pytest tests/analysis/test_failure_report.py -q
python -m pytest tests/backend/test_verify_step_contract_report.py -q
python -m pytest tests/backend/test_preload_threshold_search.py -q
python -m pytest tests --collect-only -q
```

附加人工检查：

```text
1. 检查 configs/hospital_level_profiles.json
2. 检查 configs/preload_sensitivity_matrix.csv
3. 检查 sim_status.json.resources.failure_rate
4. 检查 analysis/failure_report.json
5. 检查 analysis/preload_sensitivity_report.json
6. 检查 analysis/threshold_search_report.json
```

---

# 第七部分：如果测试通过，能够说明什么

如果 `load_factor=1.0` 下 `failure_rate < 0.1`：

> 说明该医院 profile 的 normal_patient_count 设定在系统中是可承受的。

如果 `failure_rate` 随 `load_factor` 上升而可重复上升：

> 说明系统能够反映患者负荷增加对运营失败的影响。

如果 threshold search 能找到稳定阈值：

> 说明系统已经从演示型仿真升级为容量阈值分析工具。

如果小医院 shock 测试更早失败：

> 说明低资源医院对瞬时患者冲击更敏感。

如果 failure reason decomposition 清楚：

> 说明系统不仅能判断是否失败，还能解释失败原因，为后续资源干预提供依据。

---

# 第八部分：局限性

1. 当前公开资料支持医患比/护患比作为急诊运营指标，但不一定提供全国统一硬性标准数值。
2. 本文的医患比/护患比为 engineering default，后续应由 `ed_staffing_evidence_table.md` 填入真实数值替换。
3. 当前系统的 `burst` 更接近连续高倍率到达，不等同于单 step 瞬时批量到达。
4. 当前系统尚未完整实现 patient-level `failure_rate`。
5. 若缺少 `triage_completed_at / first_doctor_contact_at / ed_exit_at`，CTAS violation 与 ED LOS 只能先做保守判定。
6. 不应随机生成死亡率。
7. 严重结局只能在系统已有 explicit event 时进入 `critical_outcome_event`。
8. `failure_threshold=0.1` 是项目 stress-test red line，不是现实医院官方阈值。
9. 本轮不实现完整 ICU / ward / OR 仿真，只保留 downstream interface stub。

---

# 第九部分：最终结论

本 implementation 将 Week13 的核心任务明确为：

> 基于真实 ED 运营指标和工程默认 hospital profiles，固定医生/护士数量，以患者数量为变量，构建资源瓶颈测试框架；通过 composite failure rate 与 coarse-to-fine threshold search 找到不同医院等级下的系统失效阈值。

最终系统应回答：

```text
在 large / medium / small ED 场景下，
当患者负荷达到 normal 的多少倍时，
failure_rate 超过 0.1？
主导 failure 的原因是什么？
系统瓶颈是医生、护士、检查流程，还是 boarding 出口堵塞？
```

这就是 Week13 的核心交付。
