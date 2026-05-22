# Week 9 初始化说明

## 第一部分：`week9_v1` 当前内容与已完成功能

### 1. 当前唯一工作根目录

Week 9 后续开发统一以以下目录作为唯一主线工作根目录：

```text
D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\_tmp_week9_cleanup\week9_v1
```

它是从 Week 8 merge system 清理出来的干净版本，用于继续推进 Week 9 的 ED-HIS 开发。  
原始 `week8/` 目录现在只作为历史参考、旧文档回查和运行产物对照，不再作为主开发目录。

### 2. 当前保留的核心模块

- `reverie/backend_server/`
  Auto Mode 主后端，负责仿真、人物状态推进、资源队列、病人流程、地图 movement/environment 文件写出。

- `app_core/app/`
  User Mode 主后端，负责问诊状态机、LLM 接入、RAG、handoff、encounter API 等。

- `app_core/memory/`
  Memory v1 基础设施层，负责统一 schema、storage、service、retrieval、audit、handoff snapshot 等能力。

- `environment/frontend_server/`
  Django + Phaser 前端宿主层，负责 mode 控制、页面渲染、live dashboard、2D 地图播放。

- `environment/react_frontend/`
  React + R3F/Three.js viewer，作为独立 3D/可视化前端链路存在。

### 3. 到目前为止已经完成的功能

#### Auto Mode

- Auto mode 已可稳定执行 `run 100`。
- Auto 仿真链路保留了 Week 8 的核心能力：
  - 病人生成与流转
  - zone / queue / resource 模拟
  - boarding timeout 逻辑
  - dashboard 运行态写盘
- Auto mode 的 Memory Hooks 已经从最小安全版扩展到更完整的事件层，当前已接入：
  - `encounter_started`
  - `resource_bottleneck`
  - `boarding_timeout`
  - `encounter_closed`
  - `disposition_decided`
  - `handoff_requested`
  - `handoff_completed`
  - `next_slot`

#### User Mode

- User mode 的回归测试已通过。
- User API 连续交互可以持续运行，不会在短程连续操作中崩溃。
- User mode 仍保留：
  - LLM + doctor-only RAG
  - handoff 状态机
  - encounter 生命周期
  - Memory v1 写入

#### Memory v1

- Memory v1 的 substrate 已存在并可工作：
  - `events.jsonl`
  - `audit.jsonl`
  - `current/`
  - `snapshots/`
- 当前 runtime data 根路径为：

```text
D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\_tmp_week9_cleanup\week9_v1\runtime_data
```

- 其中实际 Memory v1 写盘位置为：

```text
D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\_tmp_week9_cleanup\week9_v1\runtime_data\memory
```

### 4. Week 9 继续开发时最关键的代码路径

- `app_core/memory/schema.py`
- `app_core/memory/service.py`
- `app_core/memory/storage.py`
- `app_core/app/api_v1.py`
- `reverie/backend_server/reverie.py`
- `reverie/backend_server/persona/persona_types/patient.py`
- `reverie/backend_server/auto_memory_hooks.py`

这些文件是理解 Week 8 已交付能力、并继续推进 Week 9 ED-HIS 的最重要起点。

---

## 第二部分：Week 9 参考仓库说明

### 1. 参考仓库目录

本地参考仓库统一放在：

```text
D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\_tmp_week9_cleanup\week9_v1\reference
```

当前参考目录包括：

- `reference/BME_1325_Group4_repo`
  - Group4 的 ICU / PostgreSQL-first / backend 设计参考。

- `reference/bahmni`
  - 按本轮指定路径放置的 `OpenEMR` 参考仓库。
  - 注意：这里目录名叫 `bahmni`，但仓库内容实际来自 `openemr/openemr`。

- `reference/openhospital`
  - OpenHospital 参考仓库。

- `reference/bahmni_reference_backup`
  - 为避免覆盖原先已存在的 Bahmni 参考仓库而保留的备份副本。
  - 仅作补充阅读，不参与主线实现。

### 2. 这些参考仓库分别用来看什么

结合 `week9_his_dev_readme_v2.md` 的意图，这些 reference 仓库的用途如下：

- `reference/BME_1325_Group4_repo`
  - 重点参考：
    - PostgreSQL-first 数据层思路
    - service boundary
    - schema discipline
    - backend API 组织方式

- `reference/bahmni`（实际为 OpenEMR）
  - 重点参考：
    - API 专业化
    - 文档组织方式
    - 配置与环境组织
    - 医疗系统大仓库如何分层

- `reference/openhospital`
  - 重点参考：
    - 传统 HIS 的实体组织
    - 患者、就诊、流程、科室、结果等对象关系
    - 经典医院信息系统目录结构

- `reference/bahmni_reference_backup`
  - 重点参考：
    - 模块化 HIS/EMR/LIS 组织方式
    - 前后端模块拆分思路
  - 这是保留下来的旧 Bahmni 参考，不是本轮要求的主 reference 路径。

### 3. 使用 reference 仓库时必须遵守的边界

这些参考仓库只用于“看设计”，不能直接进入主线运行时。必须遵守以下规则：

- 不把 reference 仓库复制进主线业务目录。
- 不直接 import 它们的运行时代码。
- 不在主线里直接 graft ICU-specific schema。
- 不在主线里直接 graft 商业 HIS 全量模块。
- 只把它们当作：
  - 架构参考
  - 目录组织参考
  - 数据层参考
  - 接口层参考

换句话说，Week 9 的任何正式实现都必须落在 `week9_v1/` 主代码树中，而不是依赖 `reference/` 下的代码直接运行。

### 4. Developer B 在 Week 9 的起步重点

作为 Developer B，后续重点应放在：

- `app_core/his/adapters/`
- `tests_his/`
- ED workflow -> HIS service integration
- contract alignment
- timeline export
- golden-path smoke tests

Developer B 的职责是：

- 读取并理解 A 已冻结的 substrate / contract
- 在主线代码树中补齐 adapter、integration 和 validation
- 通过测试证明：
  - Memory v1 -> HIS 的升级路径是可行的
  - user/auto workflow 到 HIS service 的对接是正确的
  - contract 字段解释是一致的

而不是：

- 另起一套平行 schema
- 直接修改 A 的 storage / service 真源设计
- 把 reference 仓库代码直接接进主线

---

## 建议的 Week 9 阅读顺序

1. `week9_his_dev_readme_v2.md`
2. `week9_his_developer_B_spec_v2.md`
3. `week9_his_merge_protocol_v2.md`
4. `app_core/memory/*`
5. `app_core/app/api_v1.py`
6. `reverie/backend_server/reverie.py`
7. `reverie/backend_server/persona/persona_types/patient.py`
8. `reference/` 下的参考仓库

如果新开任何一个对话，建议先阅读本文件，再开始 Week 9 的具体实现工作。
