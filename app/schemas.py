from typing import Any, Literal

from pydantic import BaseModel, Field

TriageLevel = Literal["红区", "黄区", "绿区"]
TemperatureStatus = Literal["已知", "缺失", "未知"]


class ConversationTurn(BaseModel):
    role: Literal["患者", "助手"] = Field(..., description="对话角色")
    message: str = Field(..., description="该轮对话内容")


class IntakeInput(BaseModel):
    chief_complaint: str = Field(..., min_length=1, description="主诉，例如：腹痛、胸痛、发热")
    age: int = Field(..., ge=0, le=120, description="年龄")
    sex: str = Field(..., description="性别，可填写：男 / 女 / 其他 / 未知")
    temperature: float | None = Field(None, description="体温，单位摄氏度；如果尚未测量可留空")
    pain_score: int = Field(..., ge=0, le=10, description="疼痛评分，0 到 10 分")
    vital_signs: dict[str, str | int | float] | None = Field(
        None,
        description="生命体征，可填写如 heart_rate、spo2、systolic_bp、respiratory_rate",
    )


class TriageRequest(IntakeInput):
    pass


class TriageResponse(BaseModel):
    triage_level: TriageLevel = Field(..., description="分诊等级：红区 / 黄区 / 绿区")
    risk_flags: list[str] = Field(default_factory=list, description="风险标记")
    need_emergency_transfer: bool = Field(..., description="是否需要立即急诊转运")
    recommended_outpatient_entry: str = Field(..., description="推荐就诊入口")
    rule_engine_hits: list[str] = Field(default_factory=list, description="规则引擎命中的安全规则")


class SessionContext(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    chief_complaint: str = Field(..., description="主诉")
    age: int = Field(..., description="年龄")
    sex: str = Field(..., description="标准化后的性别")
    temperature: float | None = Field(None, description="体温")
    temperature_status: TemperatureStatus = Field("缺失", description="体温状态：已知 / 缺失 / 未知")
    fever_present: bool | None = Field(None, description="患者是否口述存在发热；True 表示发热，False 表示未发热，None 表示未提及")
    pain_score: int = Field(..., description="疼痛评分")
    vital_signs: dict[str, str | int | float] = Field(default_factory=dict, description="生命体征")
    symptoms: list[str] = Field(default_factory=list, description="已识别症状")
    onset_time: str | None = Field(None, description="起病时间")
    duration: str | None = Field(None, description="持续时间")
    severity: str | None = Field(None, description="严重程度")
    associated_symptoms: list[str] = Field(default_factory=list, description="伴随症状")
    trauma_history: bool | None = Field(None, description="是否存在外伤史")
    suspected_risk_signals: list[str] = Field(default_factory=list, description="LLM 提示的疑似风险信号")
    risk_flags: list[str] = Field(default_factory=list, description="风险标记")
    rule_engine_hits: list[str] = Field(default_factory=list, description="规则引擎命中结果")
    triage_level: TriageLevel | None = Field(None, description="当前分诊等级")
    need_emergency_transfer: bool = Field(False, description="是否需要立即急诊转运")
    recommended_outpatient_entry: str | None = Field(None, description="推荐就诊入口")
    missing_required_fields: list[str] = Field(default_factory=list, description="仍缺失的关键字段")
    next_question: str | None = Field(None, description="下一轮追问")
    last_extraction_trace: dict[str, Any] = Field(default_factory=dict, description="上一轮自然语言特征提取轨迹")
    conversation_history: list[ConversationTurn] = Field(default_factory=list, description="对话历史")


class SessionStartResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    assistant_message: str = Field(..., description="系统下一句追问")
    triage_result: TriageResponse = Field(..., description="当前分诊结果")
    session_context: SessionContext = Field(..., description="当前会话上下文")


class SessionMessageRequest(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., min_length=1, description="患者本轮回复")


class SessionMessageResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    assistant_message: str = Field(..., description="系统下一句追问")
    extracted_updates: dict[str, Any] = Field(..., description="本轮从文本中抽取出的结构化更新")
    extraction_trace: dict[str, Any] = Field(..., description="本轮从自然语言到结构化特征的提取轨迹")
    triage_result: TriageResponse = Field(..., description="当前分诊结果")
    session_context: SessionContext = Field(..., description="当前会话上下文")


class SessionStateResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    triage_result: TriageResponse = Field(..., description="当前分诊结果")
    session_context: SessionContext = Field(..., description="当前会话上下文")


class LLMQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="发送给阿里云百炼模型的用户输入")
    system_prompt: str | None = Field(
        "你是医院分诊预问诊助手，请用中文给出清晰、简短、结构化的回答。",
        description="可选的 system prompt",
    )
    model: str | None = Field(None, description="模型名称；为空时默认使用环境变量 BAILIAN_MODEL 或默认模型")
    temperature: float = Field(0.2, ge=0, le=2, description="采样温度")
    include_raw_response: bool = Field(False, description="是否在返回中包含百炼原始响应")


class LLMQueryResponse(BaseModel):
    provider: str = Field(..., description="模型服务提供方")
    model: str = Field(..., description="实际调用的模型")
    content: str = Field(..., description="模型返回的主要文本")
    request_id: str | None = Field(None, description="百炼请求 ID")
    usage: dict[str, Any] | None = Field(None, description="Token 使用量等信息")
    raw_response: dict[str, Any] | None = Field(None, description="百炼原始响应，仅调试时返回")


