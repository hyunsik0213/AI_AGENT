from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.agent.tooling import INTENT_TOOL_REQUIREMENTS, TOOL_CATALOG

MOCK_API_BASE_URL = os.getenv("MOCK_API_BASE_URL", "http://mock_spring:8001")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "agent_admin_token")

INTENT_MODE = os.getenv("INTENT_MODE", "rule").lower()  # rule | gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

app = FastAPI(title="FastAPI Agent", version="0.4.0")


class ChatCommand(BaseModel):
    message: str


class Intent(BaseModel):
    type: Literal["LIST_INACTIVE_MEMBERS", "CREATE_SCHEDULE"]
    period_days: int | None = None
    activity_type: str | None = None
    schedule_title: str | None = None
    schedule_date: str | None = None


class ExecutionResult(BaseModel):
    intent: dict[str, Any]
    selected_tools: list[str]
    result: dict[str, Any]
    chat_message: str
    intent_mode: str


def parse_intent_rule(message: str) -> Intent:
    if "미참석" in message or "참석하지 않은" in message:
        period_match = re.search(r"(\d+)\s*주", message)
        period_days = int(period_match.group(1)) * 7 if period_match else 14
        return Intent(type="LIST_INACTIVE_MEMBERS", period_days=period_days, activity_type="ensemble")

    if "일정" in message and ("추가" in message or "등록" in message):
        date_match = re.search(r"(\d{1,2})\/(\d{1,2})", message)
        title_match = re.search(r"\d{1,2}\/\d{1,2}\s*(.+?)\s*일정", message)
        if date_match is None:
            raise HTTPException(status_code=400, detail="일정 날짜(MM/DD)를 찾지 못했습니다.")

        year = date.today().year
        parsed_date = date(year, int(date_match.group(1)), int(date_match.group(2))).isoformat()
        title = title_match.group(1).strip() if title_match else "새 일정"
        return Intent(type="CREATE_SCHEDULE", schedule_title=title, schedule_date=parsed_date)

    raise HTTPException(status_code=400, detail="현재 지원하지 않는 요청입니다.")


async def parse_intent_gemini(message: str, available_apis: list[dict[str, Any]]) -> Intent:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="INTENT_MODE=gemini 이지만 GEMINI_API_KEY가 없습니다.")

    prompt = (
        "너는 동아리 운영 AI Agent planner다. 사용자의 요청을 아래 JSON 스키마로 변환하라.\n"
        "반드시 JSON만 출력하고 다른 텍스트는 출력하지 마라.\n"
        "type은 LIST_INACTIVE_MEMBERS 또는 CREATE_SCHEDULE 중 하나만 허용한다.\n"
        "period_days/activity_type/schedule_title/schedule_date는 필요 없으면 null.\n"
        f"사용 가능한 API 목록: {json.dumps(available_apis, ensure_ascii=False)}\n"
        f"사용자 요청: {message}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["LIST_INACTIVE_MEMBERS", "CREATE_SCHEDULE"]},
                    "period_days": {"type": ["integer", "null"]},
                    "activity_type": {"type": ["string", "null"]},
                    "schedule_title": {"type": ["string", "null"]},
                    "schedule_date": {"type": ["string", "null"]},
                },
                "required": ["type", "period_days", "activity_type", "schedule_title", "schedule_date"],
            },
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Gemini(intent) 호출 실패: {resp.text}")

    content_text = _extract_gemini_text(resp.json())
    return _validate_intent_json(content_text)


async def plan_tools_gemini(intent: Intent, available_tool_names: list[str]) -> list[str]:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="INTENT_MODE=gemini 이지만 GEMINI_API_KEY가 없습니다.")

    prompt = (
        "너는 툴 플래너다. 의도와 사용 가능한 툴 목록을 보고 필요한 툴 이름 배열만 JSON으로 반환해라.\n"
        "반드시 available_tools에 있는 이름만 사용해라.\n"
        f"intent: {intent.model_dump_json()}\n"
        f"available_tools: {json.dumps(available_tool_names, ensure_ascii=False)}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "object",
                "properties": {
                    "required_tools": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["required_tools"],
            },
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Gemini(plan) 호출 실패: {resp.text}")

    content_text = _extract_gemini_text(resp.json())
    parsed = json.loads(content_text)
    selected = parsed.get("required_tools", [])
    if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
        raise HTTPException(status_code=502, detail="Gemini tool plan 포맷이 올바르지 않습니다.")
    return selected


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=502, detail="Gemini 응답에 candidates가 없습니다.")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise HTTPException(status_code=502, detail="Gemini 응답에 content parts가 없습니다.")

    content_text = parts[0].get("text", "")
    if not content_text:
        raise HTTPException(status_code=502, detail="Gemini 응답 텍스트가 비어 있습니다.")
    return content_text


def _validate_intent_json(content_text: str) -> Intent:
    try:
        return Intent.model_validate_json(content_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini intent JSON 파싱 실패: {exc}") from exc


async def get_available_apis(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    resp = await client.get(f"{MOCK_API_BASE_URL}/apis", headers=headers)
    resp.raise_for_status()
    return resp.json()["available_apis"]


def _api_tools_from_backend(available_apis: list[dict[str, Any]]) -> list[str]:
    backend_names = {api["name"] for api in available_apis}
    catalog_names = set(TOOL_CATALOG.keys())
    return sorted(list(backend_names & catalog_names))


async def build_intent(message: str, available_apis: list[dict[str, Any]]) -> Intent:
    if INTENT_MODE == "gemini":
        return await parse_intent_gemini(message, available_apis)
    return parse_intent_rule(message)


async def choose_tools(intent: Intent, available_apis: list[dict[str, Any]]) -> list[str]:
    available_tool_names = _api_tools_from_backend(available_apis)

    if INTENT_MODE == "gemini":
        selected_tools = await plan_tools_gemini(intent, available_tool_names)
    else:
        selected_tools = INTENT_TOOL_REQUIREMENTS.get(intent.type, [])

    missing = [name for name in selected_tools if name not in available_tool_names]
    if missing:
        raise HTTPException(status_code=403, detail=f"권한 또는 API 부족: {missing}")

    if not selected_tools:
        raise HTTPException(status_code=400, detail="선정된 툴이 없습니다.")

    return selected_tools


async def execute_workflow(intent: Intent, selected_tools: list[str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        if intent.type == "LIST_INACTIVE_MEMBERS":
            if not {"get_members", "get_activities"}.issubset(set(selected_tools)):
                raise HTTPException(status_code=400, detail="LIST_INACTIVE_MEMBERS에는 get_members/get_activities가 필요합니다.")

            to_date = date.today()
            from_date = to_date - timedelta(days=intent.period_days or 14)

            members_resp = await client.get(f"{MOCK_API_BASE_URL}/members", params={"status": "active"}, headers=headers)
            members_resp.raise_for_status()
            members = members_resp.json()["items"]

            acts_resp = await client.get(
                f"{MOCK_API_BASE_URL}/activities",
                params={"type": intent.activity_type or "ensemble", "from": from_date.isoformat(), "to": to_date.isoformat()},
                headers=headers,
            )
            acts_resp.raise_for_status()
            activities = acts_resp.json()["items"]

            attended_ids: set[int] = set()
            for activity in activities:
                attended_ids.update(activity["participant_ids"])

            inactive = [m for m in members if m["id"] not in attended_ids]
            if inactive:
                names = ", ".join(member["name"] for member in inactive)
                message = f"최근 {intent.period_days}일 기준 합주 미참석 팀원은 {len(inactive)}명입니다: {names}"
            else:
                message = f"최근 {intent.period_days}일 기준 합주 미참석 팀원이 없습니다."

            return {
                "intent": intent.model_dump(),
                "selected_tools": selected_tools,
                "result": {"inactive_count": len(inactive), "inactive_members": inactive},
                "chat_message": message,
            }

        if intent.type == "CREATE_SCHEDULE":
            if "create_schedule" not in selected_tools:
                raise HTTPException(status_code=400, detail="CREATE_SCHEDULE에는 create_schedule 툴이 필요합니다.")

            resp = await client.post(
                f"{MOCK_API_BASE_URL}/schedules",
                json={
                    "title": intent.schedule_title or "새 일정",
                    "date": intent.schedule_date,
                    "category": "meeting",
                },
                headers=headers,
            )
            resp.raise_for_status()
            created = resp.json()["created"]
            return {
                "intent": intent.model_dump(),
                "selected_tools": selected_tools,
                "result": created,
                "chat_message": f"일정을 등록했어요: {created['date']} {created['title']} (id={created['id']})",
            }

    raise HTTPException(status_code=500, detail="워크플로우 실행 중 알 수 없는 오류")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "intent_mode": INTENT_MODE,
        "gemini_configured": "yes" if bool(GEMINI_API_KEY) else "no",
        "gemini_model": GEMINI_MODEL,
    }


@app.post("/chat/command/plan")
async def plan_only(body: ChatCommand) -> dict[str, Any]:
    cleaned = body.message.replace("@AI", "").strip()
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        available_apis = await get_available_apis(client, headers)

    intent = await build_intent(cleaned, available_apis)
    selected_tools = await choose_tools(intent, available_apis)

    return {
        "intent_mode": INTENT_MODE,
        "intent": intent.model_dump(),
        "available_tools": _api_tools_from_backend(available_apis),
        "selected_tools": selected_tools,
    }


@app.post("/chat/command", response_model=ExecutionResult)
async def chat_command(body: ChatCommand) -> ExecutionResult:
    cleaned = body.message.replace("@AI", "").strip()
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        available_apis = await get_available_apis(client, headers)

    intent = await build_intent(cleaned, available_apis)
    selected_tools = await choose_tools(intent, available_apis)
    payload = await execute_workflow(intent, selected_tools)
    payload["intent_mode"] = INTENT_MODE
    return ExecutionResult(**payload)
