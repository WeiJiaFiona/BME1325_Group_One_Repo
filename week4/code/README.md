# Week 4 实践：ED MAS（急诊多智能体模拟）

本目录是课程 **Week 4** 的实践代码，实现目标是搭建一个可运行、可测试的急诊科室 MAS 原型骨架，为 Week 5-12 的扩展打基础。

## Week 4 已实现内容

1. 后端服务基础能力
- 使用 FastAPI 搭建后端入口。
- 提供健康检查接口：`GET /health`。
- 提供用户模式入口接口：`POST /mode/user/encounter/start`。

2. 急诊核心规则与流程骨架
- 分诊规则（`triage_level`）与分区路由（`route_zone`）：按病情映射到 `red/yellow/green`。
- 统一就诊状态机（`EncounterStateMachine`）：约束就诊流程状态迁移。

3. 多智能体运行所需基础组件
- 事件总线 `EventBus`：统一事件写入与读取。
- 工具层动作 `order_test`：模拟临床流程中的“下达检查”动作。
- 双模式基础：
  - `Mode-U`（用户参与模式）：接收用户主诉并给出分诊结果。
  - `Mode-A`（自动模式）：自动生成患者到达事件。

4. 安全与评估基础
- 安全护栏 `guard_action`：拦截高风险医疗建议文本。
- 指标采集 `collect_snapshot` 与汇总 `reporting`：支持 KPI 统计。

5. 前端占位与课程交付文档
- 前端 App 中实现 `Mode-U / Mode-A` 切换占位。
- 新建周计划与答辩文档骨架。

6. 测试体系（TDD 结果）
- 单元测试：bootstrap / triage / state machine / tools / metrics。
- 集成测试：user mode / auto mode / safety。
- E2E 占位测试：前端 mode switch 可见性。

## Project Tree（含功能标注）

```text
week4_code_EDMAS/
├── README.md                              # 本文档：Week 4 实践说明
├── pyproject.toml                         # Python 项目配置与 pytest 路径配置
│
├── backend/
│   └── app/
│       ├── main.py                        # FastAPI 入口；health 与用户模式 API
│       ├── domain/
│       │   ├── triage_rules.py            # 分诊等级与红黄绿分区规则
│       │   └── state_machine.py           # 就诊流程状态机（统一模式流转）
│       ├── world/
│       │   └── event_bus.py               # 事件总线（事件发射/读取）
│       ├── tools/
│       │   └── actions.py                 # 工具层动作（如 order_test）
│       ├── modes/
│       │   ├── user_mode.py               # Mode-U：用户参与入口流程
│       │   └── auto_mode.py               # Mode-A：自动仿真 tick 与患者生成
│       ├── safety/
│       │   └── guardrails.py              # 高风险内容拦截护栏
│       └── metrics/
│           ├── collector.py               # KPI 快照采集
│           └── reporting.py               # KPI 聚合统计
│
├── frontend/
│   └── src/
│       ├── App.tsx                        # 前端主界面；Mode-U / Mode-A 切换
│       └── components/
│           ├── MapView.tsx                # 地图视图占位组件
│           ├── QueuePanel.tsx             # 队列面板占位组件
│           ├── UserPatientChat.tsx        # 用户患者对话框占位组件
│           └── Dashboard.tsx              # 指标仪表盘占位组件
│
├── tests/
│   ├── unit/
│   │   ├── test_bootstrap.py              # 服务健康检查测试
│   │   ├── test_triage_rules.py           # 分诊与分区规则测试
│   │   ├── test_state_machine.py          # 状态机迁移测试
│   │   ├── test_tools.py                  # 工具层事件写入测试
│   │   └── test_metrics.py                # 指标采集字段测试
│   ├── integration/
│   │   ├── test_user_mode_flow.py         # 用户模式接口流程测试
│   │   ├── test_auto_mode_flow.py         # 自动模式仿真测试
│   │   └── test_safety_constraints.py     # 安全护栏拦截测试
│   └── e2e/
│       └── test_dashboard.spec.ts         # 前端模式切换可见性测试（Playwright）
│
├── scripts/
│   └── demo_run.sh                        # Demo 启动脚本（uvicorn:18180）
│
└── docs/
    ├── milestones/
    │   └── week4-12.md                    # Week4-12 周推进与 DoD 矩阵
    └── defense/
        └── final_report.md                # 最终报告骨架（B/C/I/M/R）
```

## 当前运行方式（Week 4 原型）

```bash
cd /home/jiawei2022/BME1325/week_4_progress/week4_code_EDMAS
bash scripts/demo_run.sh
```

启动后接口：
- `http://127.0.0.1:18180/health`
- `http://127.0.0.1:18180/docs`

## Week 4 交付边界说明

本周重点是“能跑 + 可测 + 可扩展骨架”，暂未完成：
- 真实 Phaser 地图渲染与可视化联动。
- 完整医生/护士/协调员 agent 策略循环。
- 长时稳定性实验与大规模指标面板。

这些将在 Week 5-12 继续迭代。
