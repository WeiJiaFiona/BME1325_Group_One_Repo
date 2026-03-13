# 阿里云百炼 API 接入说明

## 1. 接入方式

当前项目采用阿里云百炼的 OpenAI 兼容 Chat Completions 接口：

- Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- Chat Completions 路径：`/chat/completions`
- 对应完整地址：`https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`

项目里已经封装好的文件：

- `bailian_client.py`
- `main.py`

## 2. 需要配置的环境变量

建议不要把 API Key 直接写进代码，而是配置环境变量：

- `DASHSCOPE_API_KEY`
- `BAILIAN_BASE_URL`
- `BAILIAN_MODEL`
- `BAILIAN_STRUCTURED_MODEL`

项目根目录已经提供了示例文件：

- `.env.example`

你可以参考它来配置。

## 3. Windows PowerShell 临时配置示例

当前终端临时生效：

```powershell
$env:DASHSCOPE_API_KEY="你的百炼APIKey"
$env:BAILIAN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:BAILIAN_MODEL="qwen3.5-plus"
$env:BAILIAN_STRUCTURED_MODEL="qwen-plus"
```

如果你已经把真实 Key 发到聊天里，建议到百炼控制台轮换后再使用新 Key。

## 4. 当前已经实现的能力

### 4.1 直接问模型

接口：

- `POST /llm/query`

作用：

- 直接把一段 query 发给百炼模型
- 用来验证 API 是否接通
- 用来调 system prompt / model / temperature

### 4.2 会话消息自动抽取

接口：

- `POST /session/message`

作用：

- 优先调用百炼做结构化信息抽取
- 失败时回退到本地关键词规则
- 抽取结果写回 Session Context
- 规则引擎再根据上下文重新分诊

## 5. 在 /docs 中如何测试

先启动：

```powershell
uvicorn main:app --reload
```

然后打开：

```text
http://127.0.0.1:8000/docs
```

### 5.1 直接测试百炼模型

`POST /llm/query`

请求体示例：

```json
{
  "query": "请用中文总结：8岁女孩腹痛伴发热应该优先关注哪些分诊信息？",
  "system_prompt": "你是医院分诊预问诊助手，请用中文简明回答。",
  "temperature": 0.2,
  "include_raw_response": false
}
```

### 5.2 测试多轮分诊会话

先调用：

- `POST /session/start`

再调用：

- `POST /session/message`

如果已经配置好 `DASHSCOPE_API_KEY`，这一步会优先调用百炼做结构化抽取。

## 6. 代码入口

百炼 API 直连逻辑：

- `bailian_client.py`

主流程接入点：

- `main.py` 中的 `/llm/query`
- `main.py` 中的 `extract_updates_from_message()`
- `main.py` 中的 `/session/message`
