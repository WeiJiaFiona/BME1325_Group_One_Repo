# Week 9 ED-HIS 并行开发简要说明

## 1. 先回答一个问题：上一版 proposal 里是否已经包含测试方式

包含，但还不够适合双人并行开发直接落地。

上一版 proposal 已经写到了：
- 数据层 / API / 事件层需要做哪些测试；
- 如何验证 Memory v1 到 HIS 的升级路径；
- 如何做 contract alignment；
- 如何做 STEMI golden-path smoke test。

但它还没有进一步拆成：
1. **Developer A 与 Developer B 的明确边界**；
2. **两个人各自负责哪些测试**；
3. **哪些 contract 必须先冻结再开工**；
4. **最终如何减少 merge 冲突**。

因此，本轮文档的目标，是把上一版 proposal 拆成：
- A 的可并行 implementation spec；
- B 的可并行 implementation spec；
- A/B 最终合并规范；
- 以及一份给开发者的统一说明。

---

## 2. 本轮开发的统一根目录

所有 Week 9 HIS 开发必须在以下目录进行：

```text
/home/jiawei2022/BME1325/week8/merge
```

不要回到：
- `/home/jiawei2022/BME1325/week8/user_mode`
- `/home/jiawei2022/BME1325/week8/auto`

继续写运行时代码。

---

## 3. 建议 clone 的参考仓库与目录位置

## 3.1 必须 clone 的参考仓库

### A. Group4 ICU/PostgreSQL 参考仓库
建议位置：

```text
/home/jiawei2022/BME1325/week8/reference/BME_1325_Group4_repo
```

建议命令：

```bash
git clone https://github.com/XanderZhou2022/BME_1325_Group4_repo.git \
  /home/jiawei2022/BME1325/week8/reference/BME_1325_Group4_repo
```

主要参考：
- `system/backend/api/`
- `system/backend/数据规范/`
- `system/backend/测试数据库/`
- `system/backend/api/README.md`

用途：
- PostgreSQL-first 后端组织方式；
- API 边界；
- 数据规范文档写法；
- seed/init/test DB 组织方式；
- event table / admission-oriented 设计参考。

### B. Open-source HIS 参考仓库（建议 clone，但非必须作为运行依赖）

为了避免仓库太大，建议只在本机 `reference/` 下保留，不进入主线代码。

建议位置：

```text
/home/jiawei2022/BME1325/week8/reference/openemr
/home/jiawei2022/BME1325/week8/reference/bahmni
/home/jiawei2022/BME1325/week8/reference/openhospital
```

建议命令：

```bash
git clone https://github.com/openemr/openemr.git \
  /home/jiawei2022/BME1325/week8/reference/openemr

git clone https://github.com/Bahmni/openmrs-module-bahmniapps.git \
  /home/jiawei2022/BME1325/week8/reference/bahmni

git clone https://github.com/informatici/openhospital.git \
  /home/jiawei2022/BME1325/week8/reference/openhospital
```

用途：
- OpenEMR：API 规范、部署方式、文档化风格；
- Bahmni：模块拆分、注册/EMR/LIS 关系；
- OpenHospital：轻量 HIS 的功能边界与目录组织。

## 3.2 不要做的事

- 不要把这些 reference 仓库直接复制进 `merge/`；
- 不要直接 import 这些仓库的运行时代码；
- 不要在主线实现里直接 graft ICU-specific schema 或商业 HIS 全量模块；
- 这些仓库仅作为 **架构、目录、数据层、接口层** 参考。

---

## 4. 统一实现目标（A/B 都必须认同）

本轮不是单纯把 Memory v1 改成 SQL，也不是做一个完整商业 HIS。

本轮的统一目标是：

> 在现有 ED-MAS + Memory v1 的基础上，建设一个 **ED-HIS v1**，使系统具备：
> - 患者与就诊主索引；
> - 分诊、生命体征、医嘱、检验、影像、handoff 的正式落库；
> - 文档与事件注册；
> - SQL-backed 持久层；
> - 对齐老师接口契约 v1.0 的 API 与事件发布；
> - 审计、权限与可回放能力。

---

## 5. 双人并行开发的总原则

### Developer A 重点
- HIS substrate / schema / SQL / service layer / registry / outbox / audit / auth

### Developer B 重点
- 现有 ED 流程与 HIS 的接线；
- Memory v1 向 HIS 的升级适配；
- user-mode 与后续 auto-mode 的 integration；
- contract smoke test；
- timeline / replay / handoff / golden-path 验证。

### 双方都不能做的事
- 各自写一套不同 schema；
- 各自定义不同的 patient_id / encounter_id；
- 各自直接写 DB 而绕过 service layer；
- 修改老师接口契约的硬约束；
- 把 reference 仓库直接变成主线依赖。

---

## 6. A/B 开工前必须冻结的 contract

1. `patient_id` / `encounter_id` 格式
2. 外部状态字典
3. CTAS 与 zone
4. 事件 envelope
5. SQL 主表 schema 命名
6. HIS service 层公共方法名
7. Memory → HIS adapter 输入输出格式
8. transfer / admission / timeline / summary API 路由

没有冻结前，不要大面积并行编码。

---


## 6.5 最小串行开发 gate（必须先完成，再高度并行）

本轮开发**不是完全零依赖并行**，而是：

> **A 先交付最小 HIS 底座与 contract freeze，B 再开始全面接线；此后两边再高度并行。**

### A 必须先交付给 B 的最小集合

在 B 开始深度开发前，A 至少必须先交付并冻结以下内容：

1. `app_core/his/schemas/*` 初版
   - 至少包含：`patient.py`、`encounter.py`、`triage.py`、`order.py`、`lab.py`、`imaging.py`、`handoff.py`、`audit.py`
2. `app_core/his/storage/base.py`
   - 冻结 storage interface
3. `app_core/his/services/*` 可 import 的空壳与函数签名
   - B 不要求 A 先写完所有逻辑，但必须可 import、可调用、命名稳定
4. `sql/postgres/001_core_master_tables.sql`
5. `sql/postgres/002_encounter_tables.sql`
6. `sql/postgres/003_order_result_tables.sql`
7. `app_core/his/adapters/memory_adapter.py` 的输入/输出 contract 定义
   - 至少明确 `MemoryItem`、`CurrentEncounterSummary`、`HandoffMemorySnapshot` 如何映射到 HIS
8. 与接口契约 v1.0 对齐的关键字段与路由冻结
   - `patient_id`
   - `encounter_id`
   - CTAS / zone
   - transfer / admissions / summary / timeline routes
   - event envelope

### 在 A 交付上述最小集合之前，B 只能做什么

B 在 A 完成上述最小底座前，**不要猜测接口直接深度推进**。此阶段 B 只应做：

- `tests_his/` 测试脚手架
- `memory_adapter.py` 和 `contract_adapter.py` 的占位文件与字段映射草稿
- contract alignment 的文档准备
- golden path / STEMI 脚本设计
- timeline export 的非实现性规划

### 在 A 交付上述最小集合之后，B 才全面展开

A 完成最小底座以后，B 才正式开始：

- ED workflow → HIS service 接线
- Memory v1 → HIS upgrade path 落地
- transfer / admission / summary / timeline API smoke
- contract smoke tests
- golden-path 演示与量化报告

### 为什么必须这样做

如果 B 在 A 交付最小底座前就自行推测：
- schema
- table names
- service signatures
- Memory → HIS 映射

最终很容易造成：
- 两套 schema
- 两套 service 命名
- 大量 merge 冲突
- golden path 无法稳定联调

---

## 7. 推荐的协作节奏

### 第一步
A 先产出：
- `app_core/his/schemas/*`
- `app_core/his/storage/*`
- `app_core/his/services/*` 的空壳 + 最小接口
- SQL migrations 初版

### 第二步
B 同时产出：
- `app_core/his/adapters/memory_adapter.py`
- `app_core/his/adapters/contract_adapter.py`
- `tests_his/test_memory_upgrade_path.py`
- `tests_his/test_contract_alignment.py`
- `scripts/run_his_contract_smoke.py`

### 第三步
A/B 再在同一根目录做集成与修补。

---

## 8. 你们应该如何给 Codex 开 plan 模式

### Developer A
使用 `week9_his_developer_A_spec.md`

### Developer B
使用 `week9_his_developer_B_spec.md`

### 双方 merge 前
共同阅读 `week9_his_merge_protocol.md`

---

## 9. 当前阶段的成功标准

如果以下条件都满足，可以认为本轮双人并行开发成功：

- A 的 SQL/HIS substrate 可运行；
- B 的 memory-upgrade adapter 可运行；
- contract smoke test 通过；
- patient / encounter / transfer / admission / summary / timeline API 可调用；
- Memory v1 的 event/summary/handoff 能写入 HIS；
- STEMI golden-path 至少可跑通 ED 侧主链路；
- A/B 代码可在同一 `merge/` 根目录下无冲突合并。
