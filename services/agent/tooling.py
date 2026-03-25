from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IntentType = Literal["LIST_INACTIVE_MEMBERS", "CREATE_SCHEDULE"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    required_scope: str


TOOL_CATALOG: dict[str, ToolSpec] = {
    "get_members": ToolSpec(
        name="get_members",
        description="활성/비활성 회원 목록을 조회한다.",
        required_scope="READ_MEMBER",
    ),
    "get_activities": ToolSpec(
        name="get_activities",
        description="기간 내 활동 목록을 조회한다.",
        required_scope="READ_ACTIVITY",
    ),
    "create_schedule": ToolSpec(
        name="create_schedule",
        description="일정을 등록한다.",
        required_scope="CREATE_SCHEDULE",
    ),
    "update_member_status": ToolSpec(
        name="update_member_status",
        description="회원 상태를 변경한다.",
        required_scope="UPDATE_MEMBER_STATUS",
    ),
}


INTENT_TOOL_REQUIREMENTS: dict[IntentType, list[str]] = {
    "LIST_INACTIVE_MEMBERS": ["get_members", "get_activities"],
    "CREATE_SCHEDULE": ["create_schedule"],
}
