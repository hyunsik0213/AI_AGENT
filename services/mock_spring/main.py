from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = APP_ROOT / "data"

app = FastAPI(title="Mock Spring API", version="0.1.0")


class UpdateStatusRequest(BaseModel):
    status: str


class CreateScheduleRequest(BaseModel):
    title: str
    date: str
    category: str = "meeting"


def _load_json(file_name: str) -> Any:
    with (DATA_DIR / file_name).open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(file_name: str, payload: Any) -> None:
    with (DATA_DIR / file_name).open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def get_scopes(authorization: str = Header(default="")) -> set[str]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1]
    tokens = _load_json("tokens.json")
    scopes = tokens.get(token)
    if scopes is None:
        raise HTTPException(status_code=403, detail="Invalid token")
    return set(scopes)


def require_scope(required_scope: str):
    def _checker(scopes: set[str] = Depends(get_scopes)) -> None:
        if required_scope not in scopes:
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")

    return _checker


@app.get("/apis")
def list_apis(scopes: set[str] = Depends(get_scopes)) -> dict[str, Any]:
    apis = [
        {
            "name": "get_members",
            "method": "GET",
            "path": "/members",
            "scope": "READ_MEMBER",
            "description": "활성/비활성 회원 목록 조회",
        },
        {
            "name": "get_activities",
            "method": "GET",
            "path": "/activities",
            "scope": "READ_ACTIVITY",
            "description": "기간 내 활동 목록 조회",
        },
        {
            "name": "create_schedule",
            "method": "POST",
            "path": "/schedules",
            "scope": "CREATE_SCHEDULE",
            "description": "일정 등록",
        },
        {
            "name": "update_member_status",
            "method": "PATCH",
            "path": "/members/{member_id}/status",
            "scope": "UPDATE_MEMBER_STATUS",
            "description": "회원 상태 변경",
        },
    ]
    return {"available_apis": [api for api in apis if api["scope"] in scopes]}


@app.get("/members")
def get_members(
    status: str | None = Query(default=None),
    _: None = Depends(require_scope("READ_MEMBER")),
) -> dict[str, Any]:
    members = _load_json("members.json")
    if status:
        members = [m for m in members if m["status"] == status]
    return {"items": members, "count": len(members)}


@app.get("/activities")
def get_activities(
    type: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    _: None = Depends(require_scope("READ_ACTIVITY")),
) -> dict[str, Any]:
    activities = _load_json("activities.json")
    if type:
        activities = [a for a in activities if a["type"] == type]
    if from_date:
        from_d = date.fromisoformat(from_date)
        activities = [a for a in activities if date.fromisoformat(a["date"]) >= from_d]
    if to_date:
        to_d = date.fromisoformat(to_date)
        activities = [a for a in activities if date.fromisoformat(a["date"]) <= to_d]
    return {"items": activities, "count": len(activities)}


@app.post("/schedules")
def create_schedule(
    body: CreateScheduleRequest,
    _: None = Depends(require_scope("CREATE_SCHEDULE")),
) -> dict[str, Any]:
    schedules = _load_json("schedules.json")
    next_id = max((item["id"] for item in schedules), default=0) + 1
    created = {
        "id": next_id,
        "title": body.title,
        "date": body.date,
        "category": body.category,
    }
    schedules.append(created)
    _save_json("schedules.json", schedules)
    return {"created": created}


@app.patch("/members/{member_id}/status")
def update_member_status(
    member_id: int,
    body: UpdateStatusRequest,
    _: None = Depends(require_scope("UPDATE_MEMBER_STATUS")),
) -> dict[str, Any]:
    members = _load_json("members.json")
    target = next((m for m in members if m["id"] == member_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    target["status"] = body.status
    _save_json("members.json", members)
    return {"updated": target}
