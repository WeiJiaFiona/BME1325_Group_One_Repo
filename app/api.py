from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bailian_client import (
    BailianAPIError,
    BailianConfigError,
    get_bailian_base_url,
    get_bailian_chat_model,
    get_bailian_structured_model,
    is_bailian_configured,
)
from app.schemas import (
    IntakeInput,
    LLMQueryRequest,
    LLMQueryResponse,
    SessionMessageRequest,
    SessionMessageResponse,
    SessionStartResponse,
    SessionStateResponse,
    TriageRequest,
    TriageResponse,
)
from app.services.llm_service import query_model
from app.services.triage_service import get_session_state, process_session_message, single_shot_triage, start_session

BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "ui"

app = FastAPI(
    title="分诊/预问诊智能体 API",
    description="用于演示分诊会话、规则引擎兜底、阿里云百炼接入和标准化交接单输出的模块化 FastAPI 原型。",
)

app.mount("/ui-assets", StaticFiles(directory=UI_DIR), name="ui-assets")


@app.get("/", summary="查看服务状态")
def root():
    return {
        "message": "分诊智能体 API 已启动。",
        "docs": "/docs",
        "demo": "/demo",
        "health_check": "/ping",
        "triage_endpoint": "/triage/evaluate",
        "session_start_endpoint": "/session/start",
        "session_message_endpoint": "/session/message",
        "session_lookup_pattern": "/session/{session_id}",
        "llm_query_endpoint": "/llm/query",
        "llm_provider": "阿里云百炼",
        "llm_configured": is_bailian_configured(),
        "bailian_base_url": get_bailian_base_url(),
        "bailian_chat_model": get_bailian_chat_model(),
        "bailian_structured_model": get_bailian_structured_model(),
    }


@app.get("/demo", summary="演示页面")
def demo_page():
    return FileResponse(UI_DIR / "index.html")


@app.get("/ping", summary="健康检查")
def ping():
    return {"ok": True, "message": "服务运行正常"}


@app.post(
    "/llm/query",
    response_model=LLMQueryResponse,
    summary="直接调用阿里云百炼模型",
    description="用于直接测试百炼大模型调用是否连通。",
)
def llm_query(payload: LLMQueryRequest):
    try:
        result = query_model(
            query=payload.query,
            system_prompt=payload.system_prompt,
            model=payload.model,
            temperature=payload.temperature,
        )
    except BailianConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except BailianAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    raw_response = result["raw_response"] if payload.include_raw_response else None
    return LLMQueryResponse(
        provider=result["provider"],
        model=result["model"],
        content=result["content"],
        request_id=result.get("request_id"),
        usage=result.get("usage"),
        raw_response=raw_response,
    )


@app.post(
    "/triage/evaluate",
    response_model=TriageResponse,
    summary="单次分诊评估",
    description="不创建会话，直接基于当前输入返回一份初步分诊结果。",
)
def triage_evaluate(payload: TriageRequest):
    return single_shot_triage(payload)


@app.post(
    "/session/start",
    response_model=SessionStartResponse,
    summary="开始分诊会话",
    description="创建一个新的分诊会话，并返回首轮追问和初步分诊结果。",
)
def session_start_endpoint(payload: IntakeInput):
    return start_session(payload)


@app.post(
    "/session/message",
    response_model=SessionMessageResponse,
    summary="继续多轮问诊",
    description="向已创建的分诊会话继续发送患者回复，系统会优先调用百炼做结构化抽取，并用规则引擎更新分诊结果。",
)
def session_message(payload: SessionMessageRequest):
    response = process_session_message(payload.session_id, payload.message)
    if response is None:
        raise HTTPException(status_code=404, detail="未找到对应会话")
    return response


@app.get(
    "/session/{session_id}",
    response_model=SessionStateResponse,
    summary="查看会话状态",
    description="根据会话 ID 查看当前 Session Context 和分诊结果。",
)
def get_session(session_id: str):
    response = get_session_state(session_id)
    if response is None:
        raise HTTPException(status_code=404, detail="未找到对应会话")
    return response
