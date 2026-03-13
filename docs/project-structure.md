# 分诊智能体项目目录说明

## 1. 当前目录结构

```text
w2_agent/
├─ main.py
├─ bailian_client.py
├─ .env.example
├─ app/
│  ├─ __init__.py
│  ├─ api.py
│  ├─ constants.py
│  ├─ schemas.py
│  ├─ session_store.py
│  ├─ rule_engine.py
│  └─ services/
│     ├─ __init__.py
│     ├─ feature_extractor.py
│     ├─ llm_service.py
│     └─ triage_service.py
├─ ui/
│  ├─ index.html
│  ├─ styles.css
│  └─ app.js
├─ tests/
│  ├─ test_rule_engine.py
│  └─ test_session_flow.py
└─ docs/
   ├─ triage-agent-workflow.md
   ├─ triage-agent-next-steps-cn.md
   ├─ aliyun-bailian-api-integration.md
   ├─ feature-extraction-workflow.md
   └─ project-structure.md
```

## 2. 每个文件的职责

### 2.1 启动入口

- `main.py`
  - 保留最小启动入口
  - 继续支持 `uvicorn main:app --reload`

### 2.2 外部大模型接入

- `bailian_client.py`
  - 负责调用阿里云百炼 API
  - 提供 `query_bailian()`
  - 提供结构化抽取 `extract_triage_updates()`
  - 负责读取 API 配置

### 2.3 API 层

- `app/api.py`
  - 定义 FastAPI 路由
  - 提供 `/ping`、`/llm/query`、`/session/start`、`/session/message` 等接口
  - 提供 `/demo` 前端演示页面

### 2.4 数据模型层

- `app/schemas.py`
  - 定义请求、响应、`SessionContext`、`TriageResponse`
  - 包含最新的 `extraction_trace` 与 `last_extraction_trace`

### 2.5 常量层

- `app/constants.py`
  - 管理症状关键词、红旗关键词、创伤关键词、时间词等常量

### 2.6 会话存储层

- `app/session_store.py`
  - 当前为内存版会话存储
  - 后续可以替换为 SQLite

### 2.7 规则引擎层

- `app/rule_engine.py`
  - 负责红黄绿分级、红旗征象判断、隐性危重识别、边界防错和推荐就诊入口

### 2.8 服务编排层

- `app/services/feature_extractor.py`
  - 负责自然语言特征提取流水线
  - 包括：
    - 正则提取
    - 关键词提取
    - 通俗表达映射
    - LLM 补充抽取
    - 提取轨迹生成

- `app/services/llm_service.py`
  - 负责百炼结构化抽取和下一轮追问生成

- `app/services/triage_service.py`
  - 负责把特征提取结果写回 Session Context
  - 负责串联规则引擎和会话流程

### 2.9 前端演示层

- `ui/index.html`
  - 演示页面骨架

- `ui/styles.css`
  - 页面视觉样式

- `ui/app.js`
  - 与 FastAPI 接口交互
  - 显示对话、结构化特征、提取轨迹、分诊结果

### 2.10 测试层

- `tests/test_rule_engine.py`
  - 测试规则引擎核心判断

- `tests/test_session_flow.py`
  - 测试会话主流程

## 3. 这套结构如何对应 Workflow

### Step 1. 患者输入原话

对应文件：

- `ui/index.html`
- `ui/app.js`
- `app/api.py`

### Step 2. 自然语言特征提取

对应文件：

- `app/services/feature_extractor.py`
- `app/services/llm_service.py`

### Step 3. 写回 Session Context

对应文件：

- `app/services/triage_service.py`
- `app/schemas.py`
- `app/session_store.py`

### Step 4. 规则引擎复核

对应文件：

- `app/rule_engine.py`

### Step 5. 输出分诊和下一轮追问

对应文件：

- `app/services/triage_service.py`
- `app/services/llm_service.py`
- `app/api.py`

## 4. 你现在怎么运行

```powershell
uvicorn main:app --reload
```

打开文档：

```text
http://127.0.0.1:8000/docs
```

打开演示页面：

```text
http://127.0.0.1:8000/demo
```

## 5. 当前版本已经具备什么

- 多轮会话
- Session Context
- 百炼 API 接入
- 通俗表达 feature 提取
- 规则引擎兜底
- 红黄绿分诊
- 中文追问
- 前端可视化演示
- 提取轨迹展示
- 基础测试骨架

