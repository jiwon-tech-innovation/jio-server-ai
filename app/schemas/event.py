from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    """이벤트 타입 정의"""
    SMARTPHONE_DETECTED = "SMARTPHONE_DETECTED"  # 스마트폰 감지
    DROWSINESS_DETECTED = "DROWSINESS_DETECTED"  # 졸음 감지
    GAME_EXECUTED = "GAME_EXECUTED"  # 게임 실행
    GAZE_DEVIATION = "GAZE_DEVIATION"  # 시선 이탈

class EventCreateRequest(BaseModel):
    """이벤트 생성 요청"""
    user_id: str
    event_type: EventType
    metadata: Optional[str] = None  # 추가 정보 (JSON 문자열)

class EventCreateResponse(BaseModel):
    """이벤트 생성 응답"""
    id: str
    user_id: str
    event_type: str
    timestamp: datetime
    message: str = "Event recorded successfully"

class EventStatsResponse(BaseModel):
    """이벤트 통계 응답"""
    user_id: str
    total_events: int
    event_counts: dict[str, int]  # 이벤트 타입별 횟수
    period: Optional[str] = None  # 조회 기간 (예: "today", "week", "month")

class DailyEventStats(BaseModel):
    """일별 이벤트 통계"""
    date: str  # MM/DD 형식
    day_label: str  # 요일 (일, 월, 화, ...)
    phone_detections: int
    drowsy_count: int
    game_count: int
    gaze_deviation: int
    total_events: int

class WeeklyEventStatsResponse(BaseModel):
    """주간 이벤트 통계 응답"""
    user_id: str
    daily_stats: list[DailyEventStats]
    week_offset: int = 0  # 0: 이번 주, -1: 지난 주
