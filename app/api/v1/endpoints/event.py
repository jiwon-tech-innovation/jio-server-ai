from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from datetime import datetime, timedelta
from sqlalchemy import func, select
from typing import Optional
import logging
from traceback import format_exc
from app.core.database import get_db
from app.models.event_count import EventCount
from app.schemas.event import (
    EventCreateRequest,
    EventCreateResponse,
    EventStatsResponse,
    WeeklyEventStatsResponse,
    DailyEventStats,
    EventType
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 🔥 Trust score penalties for distraction events
TRUST_PENALTIES = {
    "SMARTPHONE_DETECTED": -5,
    "DROWSINESS_DETECTED": -3,
    "GAZE_DEVIATION": -2,
    "GAME_EXECUTED": -3,
}

@router.post("/events", response_model=EventCreateResponse)
async def create_event(
    request: EventCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    이벤트 발생을 기록합니다.
    스마트폰 감지, 졸음 감지, 게임 실행, 시선 이탈 등의 이벤트를 POST 요청으로 저장합니다.
    또한 해당 이벤트에 따라 Trust Score를 감소시킵니다.
    """
    try:
        # 이벤트 레코드 생성
        event = EventCount(
            user_id=request.user_id,
            event_type=request.event_type.value,
            timestamp=datetime.utcnow(),
            meta_data=request.metadata
        )
        
        db.add(event)
        await db.commit()
        await db.refresh(event)
        
        # 🔥 Trust Score 감소 처리
        event_type_str = request.event_type.value
        if event_type_str in TRUST_PENALTIES:
            try:
                from app.services.memory_service import memory_service
                penalty = TRUST_PENALTIES[event_type_str]
                memory_service.update_trust_score(request.user_id, penalty)
                logger.info(f"📉 [Trust] {request.user_id}: {penalty} for {event_type_str}")
            except Exception as trust_err:
                logger.warning(f"Failed to update trust score: {trust_err}")
        
        return EventCreateResponse(
            id=str(event.id),
            user_id=event.user_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            message="Event recorded successfully"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record event: {str(e)}")

@router.get("/events/stats", response_model=EventStatsResponse)
async def get_event_stats(
    user_id: str = Query(..., description="사용자 ID"),
    period: Optional[str] = Query("all", description="조회 기간: today, week, month, all"),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자의 이벤트 통계를 조회합니다.
    이벤트 타입별 발생 횟수를 반환합니다.
    """
    try:
        # 기간 필터 설정
        now = datetime.utcnow()
        time_filter = None
        
        if period == "today":
            time_filter = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            time_filter = now - timedelta(days=7)
        elif period == "month":
            time_filter = now - timedelta(days=30)
        # period == "all"이면 time_filter는 None (전체 기간)
        
        # 기본 쿼리
        query = select(EventCount).where(EventCount.user_id == user_id)
        
        # 기간 필터 적용
        if time_filter:
            query = query.where(EventCount.timestamp >= time_filter)
        
        # 전체 이벤트 수 조회
        total_query = select(func.count(EventCount.id)).where(EventCount.user_id == user_id)
        if time_filter:
            total_query = total_query.where(EventCount.timestamp >= time_filter)
        
        total_result = await db.execute(total_query)
        total_events = total_result.scalar() or 0
        
        # 이벤트 타입별 집계
        event_counts = {}
        for event_type in EventType:
            count_query = select(func.count(EventCount.id)).where(
                EventCount.user_id == user_id,
                EventCount.event_type == event_type.value
            )
            if time_filter:
                count_query = count_query.where(EventCount.timestamp >= time_filter)
            
            count_result = await db.execute(count_query)
            event_counts[event_type.value] = count_result.scalar() or 0
        
        return EventStatsResponse(
            user_id=user_id,
            total_events=total_events,
            event_counts=event_counts,
            period=period
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get event stats: {str(e)}")

@router.get("/events/weekly", response_model=WeeklyEventStatsResponse)
async def get_weekly_event_stats(
    user_id: str = Query(..., description="사용자 ID"),
    week_offset: int = Query(0, description="주간 오프셋: 0=이번 주, -1=지난 주"),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자의 주간 이벤트 통계를 조회합니다.
    일별로 이벤트 타입별 발생 횟수를 반환합니다.
    """
    try:
        DAYS_KR = ['일', '월', '화', '수', '목', '금', '토']
        
        # 날짜 범위 계산
        today = datetime.utcnow()
        end_date = today + timedelta(days=week_offset * 7)
        start_date = end_date - timedelta(days=6)
        
        # 7일간의 빈 데이터 초기화
        daily_stats: list[DailyEventStats] = []
        
        for i in range(7):
            date = start_date + timedelta(days=i)
            date_key = f"{date.month:02d}/{date.day:02d}"
            day_label = DAYS_KR[date.weekday()]
            
            # 해당 날짜의 시작과 끝 시간
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # 각 이벤트 타입별 카운트
            phone_count = 0
            drowsy_count = 0
            game_count = 0
            gaze_count = 0
            
            for event_type in EventType:
                count_query = select(func.count(EventCount.id)).where(
                    EventCount.user_id == user_id,
                    EventCount.event_type == event_type.value
                ).where(
                    EventCount.timestamp >= day_start,
                    EventCount.timestamp < day_end
                )
                count_result = await db.execute(count_query)
                count = count_result.scalar() or 0
                
                if event_type == EventType.SMARTPHONE_DETECTED:
                    phone_count = count
                elif event_type == EventType.DROWSINESS_DETECTED:
                    drowsy_count = count
                elif event_type == EventType.GAME_EXECUTED:
                    game_count = count
                elif event_type == EventType.GAZE_DEVIATION:
                    gaze_count = count
            
            daily_stats.append(DailyEventStats(
                date=date_key,
                day_label=day_label,
                phone_detections=phone_count,
                drowsy_count=drowsy_count,
                game_count=game_count,
                gaze_deviation=gaze_count,
                total_events=phone_count + drowsy_count + game_count + gaze_count
            ))
        
        return WeeklyEventStatsResponse(
            user_id=user_id,
            daily_stats=daily_stats,
            week_offset=week_offset
        )
    except Exception as e:
        error_detail = str(e)
        error_traceback = format_exc()
        logger.error(f"Failed to get weekly event stats: {error_detail}\n{error_traceback}")
        raise HTTPException(status_code=500, detail=f"Failed to get weekly event stats: {error_detail}")
