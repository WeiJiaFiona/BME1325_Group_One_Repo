# EDMAS Auto Mode README

## 1. 文档目的

本 README 用于代码上传后的工程说明，帮助组内成员或助教快速理解 EDMAS Auto Mode 的基本结构、运行方式、输入输出和注意事项。

本文件只描述工程链条与使用方法，不承担以下内容：

- 详细实验结果报告；
- slides 图表解读；
- 真实 benchmark 数值展示；
- patient-level 原始数据说明。

详细测试说明应放在单独文档中，例如：

- `docs/final/EDMAS_auto_mode_testing_chain_audit.md`
- `docs/final/EDMAS_auto_mode_benchmark_test_description.md`

## 2. Auto Mode 是什么

Auto Mode 是 EDMAS 中的自动急诊容量仿真模式。系统自动生成 patient agent，并按照急诊流程自动推进，不依赖人工逐患者输入。

Auto Mode 主要用于：

- 容量测试；
- 压力测试；
- 流程瓶颈分析；
- benchmark 批量运行。

与 User Mode 的区别：

- User Mode 偏交互、问答、人工驱动；
- Auto Mode 偏批量仿真、指标导出、场景对比。

基础流程链条：

```text
arrival
→ triage
→ queue / bedside / bed assignment
→ doctor first contact
→ test / treatment
→ care completion
→ exit
```

## 3. Auto Mode 总体运行链条

工程链条可概括为：

```text
scenario config / scenario CSV
→ benchmark runner
→ patient arrival generation
→ triage and queue processing
→ doctor first contact
→ care completion / exit
→ exporter
→ validator / audit
→ aggregate summary
```

各阶段作用如下：

1. `scenario config / scenario CSV`  
   定义单场景或多场景参数，包括患者规模、资源配置、burst window、critical share 等。

2. `benchmark runner`  
   读取 scenario 配置，逐场景调用底层仿真入口，组织输出目录。

3. `patient arrival generation`  
   根据场景参数生成患者 agent，并按 arrival schedule 注入运行时。

4. `triage and queue processing`  
   完成分诊、队列流转、床旁护士处理、床位分配与 doctor-visible waitlist 桥接。

5. `doctor first contact`  
   医生扫描候选患者，触发首次接触，并记录 `first_doctor_contact_minute`。

6. `care completion / exit`  
   患者进入检查、治疗、结果等待、照护完成和离院链条。

7. `exporter`  
   导出 run-level、patient-level、timeseries 等标准结果文件。

8. `validator / audit`  
   检查输出完整性，并生成 flow、CTAS priority、doctor PIA、bedside/bed 等审计结果。

9. `aggregate summary`  
   对多个场景进行汇总，形成 benchmark 层面的聚合结果。

## 4. 相关目录与关键文件

以下路径基于当前仓库实际存在文件整理。

### 4.1 运行脚本

- `scripts/cluster/run_large_tertiary_capacity_benchmark.py`
- `scripts/cluster/run_auto_capacity_benchmark.py`
- `scripts/cluster/run_one_ed_bottleneck_v1_scenario.py`
- `scripts/cluster/build_large_tertiary_capacity_benchmark.py`
- `scripts/cluster/build_auto_capacity_benchmark_scenarios.py`
- `scripts/cluster/build_minimal_closed_loop_scenarios.py`

### 4.2 配置文件

- `configs/benchmark/large_tertiary_ed_profile.json`
- `configs/benchmark/large_tertiary_ed_25run_matrix.csv`
- `configs/cluster/auto_capacity_cn_benchmark_scenarios.csv`
- `configs/cluster/auto_capacity_minimal_closed_loop_v1.csv`
- `configs/cluster/ed_doctor_stage_sweep_scenarios.csv`

### 4.3 分析与导出脚本

- `analysis/auto_capacity_benchmark_export.py`
- `analysis/large_tertiary_benchmark_exporter.py`
- `analysis/large_tertiary_benchmark_validator.py`
- `analysis/large_tertiary_aggregate_exporter.py`
- `analysis/large_tertiary_flow_audit.py`
- `analysis/large_tertiary_ctas_priority_audit.py`
- `analysis/large_tertiary_doctor_pia_audit.py`
- `analysis/large_tertiary_bedside_bed_audit.py`
- `analysis/large_tertiary_path_failure_audit.py`
- `analysis/large_tertiary_patient_trace.py`
- `analysis/pia_target_sensitivity_analysis.py`

### 4.4 核心运行时代码

- `reverie/backend_server/reverie.py`
- `reverie/backend_server/bedside_queue_guards.py`
- `reverie/backend_server/ed_priority.py`
- `reverie/backend_server/persona/persona_types/patient.py`
- `reverie/backend_server/persona/persona_types/doctor.py`
- `reverie/backend_server/persona/persona_types/triage_nurse.py`
- `reverie/backend_server/persona/persona_types/bedside_nurse.py`

### 4.5 结果目录示例

结果目录通常位于：

- `test_results/<benchmark_run_id>/`
- `cluster_outputs/<experiment_run_id>/`

常见场景目录结构：

```text
test_results/<run_id>/
  <scenario_id>/
    run_summary.json
    patient_level_results.csv
    capacity_timeseries.csv
    scenario_config.json
  aggregate/
    *.csv
    *.json
    *.md
```

## 5. 基础 benchmark 参数说明

| 参数 | 含义 |
| --- | --- |
| `hospital_profile` | 医院画像或资源配置类型 |
| `benchmark_basis` | benchmark 标准基准 |
| `seed` | 随机种子，用于复现 |
| `run_steps` | 仿真步数 |
| `actual_simulated_arrivals` | 实际生成的患者 agent 数量 |
| `standard_equivalent_patients_per_day` | 标准等效日到院量，用于 benchmark 归一化解释 |
| `simulation_scale_factor` | 实际仿真人数与标准等效人数之间的缩放关系 |
| `resource_scaling_policy` | 资源是否随患者压力缩放 |
| `doctor_count` | 医生数量 |
| `triage_nurse_count` | 分诊护士数量 |
| `bedside_nurse_count` | 床旁护士数量 |
| `bed_count` | 床位容量或床位相关总量参数 |

必须区分两个概念：

```text
actual_simulated_arrivals 是代码实际生成的患者 agent 数量。
standard_equivalent_patients_per_day 是 benchmark 标准化口径，不等于实际生成患者数。
```

常见缩放关系：

```text
simulation_scale_factor =
actual_simulated_arrivals / standard_equivalent_patients_per_day
```

## 6. 三类 Auto Mode 测试类型

### 6.1 Daily Capacity Test（日容量测试）

- 改变患者负荷倍数；
- 医护和床位资源保持固定；
- 用于评估系统日容量上限；
- 常见变量：`load_multiplier`。

### 6.2 Burst Influx Test（短时涌入测试）

- 固定患者总量；
- 改变到达时间窗口；
- 用于评估短时间集中到达时的前门分诊压力；
- 常见变量：`burst_window_min`。

### 6.3 Critical Share Test（危重比例测试）

- 固定患者总量；
- 改变 L1/L2 危重患者比例；
- 用于评估危重患者优先保障能力；
- 常见变量：`critical_share_setting`。

## 7. 核心指标说明

| 指标 | 含义 |
| --- | --- |
| `overall_sdr` | 全体患者服务达标率 |
| `critical_sdr` | L1/L2 危重患者服务达标率 |
| `arrival_to_pia_min` | 到院到医生初评的时间 |
| `pia_target_min` | 医生初评目标时限 |
| `pia_sdr_success` | 是否满足 PIA 目标 |
| `first_doctor_contact_minute` | 医生首次接触时间 |
| `no_contact_count` | 未获得医生接触的患者数 |
| `critical_contact_rate` | 危重患者获得医生接触的比例 |
| `care_completion_rate` | 完成照护流程的比例 |
| `peak_triage_queue` | 分诊队列峰值 |
| `main_bottleneck` | 自动归因的主要瓶颈 |

基础公式：

```text
SDR = 达到服务目标的患者数 / 符合统计条件的患者数
```

PIA 达标判定可写为：

```text
pia_sdr_success = arrival_to_pia_min <= pia_target_min
```

注意：

- 不要用 legacy `ctas_success_rate` 替代 official SDR；
- `main_bottleneck` 需要结合 patient-level 与 queue 证据解释。

## 8. 输入文件说明

| 输入文件 | 作用 |
| --- | --- |
| scenario CSV | 定义多个测试场景 |
| profile JSON | 定义医院资源画像 |
| scenario config JSON | 单个 run 的配置快照或导出配置 |
| seed | 控制随机性 |
| output root | 指定输出目录 |

当前本地代码推荐以 `--scenario-csv` 作为主接口。  
不要把 `--scenario-csv` 与另一套假设中的 `--matrix` 混写成同一入口。

## 9. 输出文件说明

| 输出文件 | 内容 |
| --- | --- |
| `run_summary.json` | 单个 run 的总体汇总 |
| `patient_level_results.csv` | patient-level 时间戳和状态结果 |
| `capacity_timeseries.csv` | 队列和容量时序 |
| `scenario_config.json` | 当前 run 使用的场景配置 |
| `sdr_summary.json` | SDR 统计结果 |
| `aggregate/*.csv` | 多场景聚合结果 |
| `logs/*.log` | 运行日志 |

说明：

- 某些目录中 `sdr_summary.json` 可能由 exporter/aggregate 体系替代为其他命名的 summary 文件；
- 以当前 runner 对应输出为准；
- 不要假设所有历史目录都完全同构。

## 10. 基本运行方式

### 10.1 当前推荐入口

查看帮助：

```bash
python scripts/cluster/run_large_tertiary_capacity_benchmark.py --help
```

当前本地代码推荐命令模板：

```bash
python scripts/cluster/run_large_tertiary_capacity_benchmark.py \
  --scenario-csv configs/cluster/auto_capacity_cn_benchmark_scenarios.csv \
  --output-root test_results/<run_id> \
  --run-id <scenario_id>
```

### 10.2 兼容/历史入口

```bash
python scripts/cluster/run_auto_capacity_benchmark.py \
  --scenario-csv configs/cluster/auto_capacity_cn_benchmark_scenarios.csv \
  --benchmark-output-root test_results/<run_id> \
  --run-id <scenario_id>
```

### 10.3 单场景调试入口

```bash
python scripts/cluster/run_one_ed_bottleneck_v1_scenario.py \
  --scenario-csv configs/cluster/auto_capacity_cn_benchmark_scenarios.csv \
  --row-index <row_index> \
  --output-root cluster_outputs/<run_id> \
  --backend-only
```

说明：

- `run_large_tertiary_capacity_benchmark.py` 是 large tertiary benchmark 的当前推荐入口；
- `run_auto_capacity_benchmark.py` 属于兼容/历史封装；
- `run_one_ed_bottleneck_v1_scenario.py` 用于单场景运行和底层调试。

## 11. 输出完整性检查

可使用通用检查命令确认 run 是否基本完整：

```bash
find test_results/<run_id> -name "run_summary.json" | wc -l
find test_results/<run_id> -name "patient_level_results.csv" | wc -l
find test_results/<run_id> -name "capacity_timeseries.csv" | wc -l
find test_results/<run_id> -name "sdr_summary.json" | wc -l
```

也可以按原则检查：

```text
完整 run 通常应包含 run_summary、patient_level、capacity_timeseries、scenario_config、sdr_summary 或等价 summary 文件。
```

如果是 backend-only 目录，还应注意：

- screenshot 可能只有状态文件，没有真实图片；
- aggregate 目录是否存在取决于是否执行了 exporter/aggregate 步骤。

## 12. 代码上传时建议保留/排除的内容

### 12.1 建议保留

- 源代码；
- `configs/` 中的模板配置；
- `analysis/` 脚本；
- runner 脚本；
- README / docs；
- 小型示例配置；
- `.gitignore`；
- requirements / environment 文件。

### 12.2 建议排除

- 大型 `test_results/`；
- 原始 patient-level 结果；
- 大型日志；
- screenshots；
- 个人路径配置；
- 集群账号信息；
- 临时 worker 目录；
- 缓存文件；
- `__pycache__/`；
- `.DS_Store`；
- `.env`；
- 任何密钥或 token。

建议检查 `.gitignore` 是否覆盖以下模式：

```gitignore
test_results/
cluster_outputs/
logs/
screenshots/
*_raw/
*_workers/
__pycache__/
*.pyc
.env
.DS_Store
```

如果仓库已有 `.gitignore`，建议在现有基础上补充，不要直接覆盖。

## 13. 注意事项与限制

- 不要混淆实际患者数和标准等效患者数；
- 不要用 legacy 指标替代 official SDR；
- `main_bottleneck` 必须结合 patient-level 和 queue 证据解释；
- metadata-only 字段不能直接当作 runtime 结论；
- 单 seed 运行不能代表多 seed 统计结论；
- backend-only 路径下，screenshots 可能并不完整；
- 详细实验结果和 slides 解释应放在单独 benchmark test description 文档中。

## 14. 相关文档

当前仓库中建议优先阅读：

- `docs/final/EDMAS_auto_mode_testing_chain_audit.md`
- `docs/final/EDMAS_auto_mode_benchmark_test_description.md`

如果后续新增结果说明文档，建议将：

- 工程 README
- 测试链条审计
- benchmark 测试说明

三类文档分开维护，不要混写。
