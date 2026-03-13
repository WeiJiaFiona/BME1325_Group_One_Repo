# 分诊智能体当前状态、下一步与完整 Workflow

## 1. 当前状态判断

当你执行：

```bash
uvicorn main:app --reload
```

然后访问根路径 `/`，得到：

```json
{
  "message": "Triage Agent API is running.",
  "docs": "/docs",
  "health_check": "/ping",
  "triage_endpoint": "/triage/evaluate"
}
```

这说明：

- `uvicorn` 已经成功启动
- `main.py` 中的 `app = FastAPI(...)` 已经被正确加载
- 根路由 `/` 已经正常注册
- 当前服务可以正常接收 HTTP 请求

也就是说，当前最小 FastAPI 服务已经能正常工作。

## 2. 现在还不代表什么

虽然服务已经跑起来了，但这还只是“最小闭环”的第一步，不代表整个分诊智能体已经完成。

目前只说明：

- API 框架正常
- 能返回 JSON
- 可以打开交互文档继续测试

目前还没有真正完成的部分包括：

- 多轮对话采集
- Session Context 持久化
- 体温强制补问
- 红黄绿分诊规则
- 隐性危重识别
- 规则引擎兜底
- 科室边界防错

## 3. 建议你立刻做的验证

先确认下面几个地址都正常：

### 3.1 健康检查

访问：

uvicorn main:app --reload

```text
http://127.0.0.1:8000/ping
```

预期结果：

```json
{"ok": true}
```

### 3.2 交互文档

访问：

```text
http://127.0.0.1:8000/docs
```

如果能打开 Swagger UI，说明你已经具备“在浏览器里测试 API”的能力。

### 3.3 最小分诊接口

在 `/docs` 中测试：

`POST /triage/evaluate`

示例请求体：

```json
{
  "chief_complaint": "abdominal pain and fever",
  "age": 8,
  "sex": "female",
  "temperature": 38.5,
  "pain_score": 6
}
```

预期行为：

- 返回一个 triage JSON
- 至少包含 `triage_level`
- 至少包含 `risk_flags`
- 至少包含 `need_emergency_transfer`
- 至少包含 `recommended_outpatient_entry`

## 4. 当前项目所处阶段

你现在处在：

`阶段 1：最小 API 骨架已跑通`

接下来应该进入：

`阶段 2：把分诊 Workflow 真正落到接口结构和状态管理里`

## 5. 下一步应该做什么

推荐按下面顺序推进。

### Step 1. 定义 Session Context

先把整个分诊过程中要持续累积的数据结构固定下来。

建议字段：

- `session_id`
- `chief_complaint`
- `age`
- `sex`
- `temperature`
- `pain_score`
- `vital_signs`
- `symptoms`
- `onset_time`
- `duration`
- `severity`
- `associated_symptoms`
- `trauma_history`
- `risk_flags`
- `triage_level`
- `need_emergency_transfer`
- `recommended_outpatient_entry`
- `missing_required_fields`

这一步的意义是：

- 后续多轮对话每一轮都往这个对象里补数据
- 规则引擎和 LLM 都围绕这个对象工作

### Step 2. 把“单次分诊接口”升级为“多轮对话接口”

当前只有一个：

- `POST /triage/evaluate`

接下来建议拆成：

- `POST /session/start`
- `POST /session/message`
- `POST /triage/evaluate`
- `GET /session/{session_id}`

这样才能支持：

- 首轮建会话
- 每轮追问更新上下文
- 最终输出交接单

### Step 3. 先做规则引擎骨架

在没有接 LLM 前，也可以先把最重要的安全规则写出来。

第一批建议规则：

- 体温缺失时，不能直接完成普通分诊
- 胸痛 + 呼吸困难 -> Red
- 昏迷/意识不清 -> Red
- 严重外伤/大出血 -> Red
- 小于 10 岁女孩腹痛 -> 优先儿科，不直接妇科
- 疼痛评分 >= 9 -> 至少 Yellow，必要时 Red

这一步非常重要，因为任务里明确要求：

- 红旗征象要由规则引擎二次确认
- 易混淆科室要做边界防错

### Step 4. 接入 LLM

LLM 在这个任务里的职责不是“直接诊断疾病”，而是：

- 理解自然语言
- 从患者回答中提取结构化字段
- 决定下一轮最该问什么
- 生成简短分诊摘要

LLM 的输出建议尽量结构化，例如：

```json
{
  "extracted_fields": {
    "symptoms": ["abdominal pain", "fever"],
    "duration": "2 days",
    "severity": "moderate"
  },
  "next_question": "Do you have vomiting or diarrhea?",
  "suspected_risk_flags": ["pediatric_case"]
}
```

### Step 5. 把 LLM 和规则引擎串起来

推荐执行方式：

1. 患者说一句
2. API 调 LLM 提取信息
3. 更新 Session Context
4. 调规则引擎检查风险
5. 如果命中 Red，立即终止普通流程
6. 如果没命中 Red，返回下一轮追问

### Step 6. 完成最终交接单输出

最终输出要固定成标准结构：

```json
{
  "triage_level": "Red | Yellow | Green",
  "risk_flags": [],
  "need_emergency_transfer": false,
  "recommended_outpatient_entry": ""
}
```

这就是任务 2.1.2 的核心输出。

## 6. 整个 Triage Agent 的完整 Workflow

下面是建议你采用的完整流程。

### 阶段 A：患者进入系统

输入内容：

- 主诉
- 年龄
- 性别
- 生命体征
- 疼痛评分

系统动作：

- 创建 `session_id`
- 初始化 Session Context
- 检查体温是否缺失

### 阶段 B：首轮安全扫描

系统同时做两件事：

- LLM 理解患者输入
- 规则引擎检查明显红旗征象

如果发现以下情况之一，可直接进入红区：

- 胸痛伴呼吸困难
- 昏迷/抽搐
- 大出血
- 脑卒中样表现
- 严重外伤

输出动作：

- `triage_level = Red`
- `need_emergency_transfer = true`

### 阶段 C：多轮追问

如果首轮没有直接 Red，则开始多轮问诊。

LLM 负责追问：

- 什么时候开始
- 症状持续多久
- 疼痛部位
- 疼痛强度
- 是否发热
- 是否恶化
- 是否伴有呕吐、出血、嗜睡、呼吸困难
- 是否有外伤史

每轮结束后：

- 更新 Session Context
- 重新运行规则引擎
- 检查缺失字段

### 阶段 D：隐性危重识别

这里是任务中的重点。

示例：

- 车祸后极度口渴 + 嗜睡

LLM 先识别这种“异常组合信号”，生成 `suspected_risk_flags`。

然后规则引擎进一步判断：

- 是否需要升级 Red
- 是否需要紧急转运

### 阶段 E：边界防错

在推荐科室前，必须先做边界判断。

典型规则：

- 小于 10 岁女孩腹痛 -> 儿科优先
- 男性下腹痛 -> 不能误分到妇科
- 儿童发热 -> 儿科优先
- 外伤相关主诉 -> 急诊优先

### 阶段 F：强制体温补齐

在最终输出前检查：

- `temperature` 是否存在

如果没有：

- 再次追问体温
- 如果患者不知道，记录 `unknown`

注意：

- 红区病例不能因为没量体温而延迟处理

### 阶段 G：分级

根据上下文和规则结果给出：

- `Red`：危重，需立即急诊/转运
- `Yellow`：急症，需尽快处理
- `Green`：普通，可走常规门诊

### 阶段 H：输出交接单

最终系统返回：

- `triage_level`
- `risk_flags`
- `need_emergency_transfer`
- `recommended_outpatient_entry`

可选附加：

- `session_summary`
- `missing_required_fields`
- `rule_engine_log`

## 7. 你当前最合理的开发顺序

按任务推进，最推荐的开发顺序是：

1. 保持当前 FastAPI 能启动
2. 增加 `Session Context` 数据模型
3. 增加 `/session/start` 和 `/session/message`
4. 写第一版规则引擎
5. 再接 LLM
6. 最后补测试病例和自动化测试

## 8. 一句话总结

你现在已经不是“卡住”，而是已经完成了第一步：服务启动成功。

下一步不是继续纠结 `uvicorn`，而是开始把这个最小 API 骨架升级成真正的分诊智能体流程：

`单接口 -> 会话化 -> 规则引擎 -> LLM -> 完整分诊交接单`
