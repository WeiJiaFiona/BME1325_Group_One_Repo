# Executive Summary

本文提出了一个**牙科门诊多智能体工作流系统**的工程化设计方案。系统以 **GPT-5.2 驱动的编排器（Orchestrator）**为核心，负责多轮交互、会诊决策与报告生成；以多个**专家模型服务**（全景片检测、侧位片测量、CBCT 三维分析、正畸规划等）作为可选工具，提供高精度证据。系统模拟真实门诊流程，从**患者主诉→问诊补充→分诊决策→检查推荐→影像/模型分析→多专家融合→诊断结论→报告输出**，实现从患者输入到诊疗建议的闭环。关键创新点包括多轮问诊与分诊由 LLM 主导、多模态证据的结构化汇聚，以及医生/患者双层报告生成。方案详细给出了：每个 agent 的功能/输入/输出及错误处理策略；REST/gRPC/消息队列的接口示例和 JSON Schema；现有模型的封装调用流程；GPT-5.2 的工具调用与多轮对话设计；数据流与状态机示意图；报告生成格式；安全合规与可解释性保障；以及评估指标和里程碑规划。本报告适合作为项目实施参考和 PPT 制作素材。

## 1. 系统总体架构与 Agent 列表

系统按职责划分为多智能体（agent）：

- **接诊与问诊 Agent**：与患者交互多轮问诊，收集主诉、病史、症状，输出结构化主诉信息（如主要症状、持续时间、疼痛位置等）。
- **分诊决策 Agent**：综合问诊结果，判断主要问题所属科室（牙周/正畸/口腔外科等），决定优先级和检查需求。
- **检查推荐 Agent**：基于分诊结果和已有信息，推荐拍片类型（全景片、侧位片、CBCT）或其他检查，输出检查单。
- **影像入库与质量控制 Agent**：接收 DICOM/影像文件，存储到系统（对象存储或 PACS）；进行质量检查（模糊度、截断等），若不合格则提示重拍。
- **专家模型 Agent**（可按需调用）：
  - **Panoramic Expert**：全景片病灶检测（输出边框、牙位、置信度）。
  - **Cephalometric Expert**：侧位片关键点检测与测量（输出 SNA/SNB/ANB 等参数、分类、置信度）。
  - **CBCT 3D Expert**：三维关键点/分割与测量（输出重要解剖标记、距离角度等、置信度）。
  - **Orthodontic Planning Expert**：正畸规划（输出牙齿目标位置、移动方案）。
- **Evidence Aggregation Agent**：将各专家模型和检查结果转换为统一证据（如各牙位发现、结构测量值），并生成 `evidence_id`用于引用。
- **GPT Orchestrator Agent**：使用 GPT-5.2，通过工具调用流程：整合病例上下文与证据，作出诊断与治疗决策，控制流程推进。
- **报告生成 Agent**：基于 Orchestrator 的结论，生成医生版结构化报告（JSON）和患者版自然语言说明。
- **审计与合规 Agent**：记录全流程日志（输入、调用、决策）、管理权限与隐私、提醒人工审核。

## 2. 接口设计

### 2.1 通信协议与数据格式

- **REST API**：对外提供统一 HTTP 接口，URL 示例：`POST /cases/{case_id}/tools/run`，使用 JSON Body。【`application/json`】
- **gRPC**：内部微服务间通信可使用 gRPC（定义 `.proto` 文件）。
- **消息队列**：对于耗时任务（如CBCT分析），使用 Kafka/RabbitMQ 发布-订阅模式，主题如 `study.received`、`analysis.completed`。

### 2.2 JSON Schema 示例

**Case 对象 Schema**（部分示例）：

```json
{
  "type": "object",
  "required": ["case_id", "patient_info", "symptoms", "state"],
  "properties": {
    "case_id": {"type": "string"},
    "patient_info": {
      "type": "object",
      "properties": {
        "patient_id": {"type": "string"},
        "age": {"type": "integer"},
        "gender": {"type": "string"}
      }
    },
    "symptoms": {
      "type": "object",
      "properties": {
        "chief_complaint": {"type": "string"},
        "history": {"type": "string"}
      }
    },
    "state": {"type": "string"}
  }
}
```


### 2.3 文件和大影像传输

* **预签名 URL + 分片上传** ：采用 S3/MinIO 对象存储。（AWS 示例：multipart upload 最佳实践 ）用户先请求获得上传 URL，再通过多部分 PUT 上传大文件。
* **Tus 协议支持可选** ：对于网络不稳定环境，可支持 Tus Resumable 协议 。
* **DICOM/NIfTI 支持** ：支持 DICOMweb（STOW-RS 接收影像、WADO-RS 获取影像 ）以及转换为 NIfTI 格式（方便深度模型输入，NIfTI-1标准详情 ）。

### 2.4 接口示例

 **创建检查单 REST 请求** ：

```http
POST /v1/cases/CASE123/order
Content-Type: application/json
{
  "type": "PANORAMIC",
  "priority": "HIGH"
}
```

 **响应** （简单示例）：

```json
{
  "order_id": "ORD456",
  "status": "CONFIRMED"
}
```

## 3. 专家模型调用与部署

### 3.1 服务化部署策略

* **容器化** ：每个模型封装为 Docker 服务。基于 [DVCTNet](https://github.com/ShanghaiTech-IMPACT/DVCTNet) 和 [CLIK-Diffusion](https://github.com/ShanghaiTech-IMPACT/CLIK-Diffusion) 要求安装对应依赖（PyTorch、CUDA、MMDetection 等）。

### 3.2 DVCTNet 调用流程

DVCTNet GitHub 提供全景片检测代码，可作为基础。模型接口示例（REST）：

```http
POST /v1/expert/dvctnet/infer
Content-Type: application/json
{
  "study_id": "STUDY789",
  "image_url": "s3://bucket/CASE123/pan.jpg",
  "score_thresh": 0.3
}
```

响应示例：

```json
{
  "model": "DVCTNet",
  "detections": [
    {"tooth": "36", "bbox": [120, 340, 210, 410], "score": 0.87}
  ],
  "confidence": 0.87,
  "artifacts": {
    "overlay": "s3://bucket/CASE123/overlay36.png"
  }
}
```

### 3.3 CLIK-Diffusion 调用流程

CLIK-Diffusion GitHub 提供了正畸规划脚本。接口示例（REST）：

```http
POST /v1/expert/clik/infer
Content-Type: application/json
{
  "mode": "FULL_TOOTH",
  "input_mesh_url": "s3://bucket/CASE123/mesh.zip"
}
```

响应示例：

```json
{
  "model": "CLIK-Diffusion",
  "landmark_transforms": [...],
  "notes": ["请复核所需的拔牙决策"],
  "confidence": 0.75
}
```

### 3.4 2D/3D 关键点模型

假设已有模型（未开源）。封装示例（gRPC）：

```proto
service CephService {
  rpc DetectLandmarks(CephRequest) returns (CephResponse);
}

message CephRequest {
  string study_id = 1;
  string image_url = 2;
}

message CephResponse {
  repeated Point landmarks = 1;
  map<string, float> measurements = 2;
}
```


