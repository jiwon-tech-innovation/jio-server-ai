from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.core.database import Base

class EventCount(Base):
    """
    이벤트 발생 횟수를 저장하는 테이블
    스마트폰 감지, 졸음 감지, 게임 실행, 시선 이탈 등의 이벤트를 기록
    """
    __tablename__ = "event_counts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, index=True, nullable=False)
    
    # 이벤트 타입: SMARTPHONE_DETECTED, DROWSINESS_DETECTED, GAME_EXECUTED, GAZE_DEVIATION
    event_type = Column(String, index=True, nullable=False)
    
    # 이벤트 발생 시간
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    
    # 추가 메타데이터 (선택적)
    # metadata는 SQLAlchemy 예약어이므로 Python 속성 이름은 meta_data로 하고, DB 컬럼 이름은 metadata로 유지
    meta_data = Column("metadata", String, nullable=True)  # JSON 문자열로 저장 가능
    
    # 인덱스: 사용자별, 이벤트 타입별, 시간별 조회 최적화
    __table_args__ = (
        Index('idx_user_event_time', 'user_id', 'event_type', 'timestamp'),
        Index('idx_user_time', 'user_id', 'timestamp'),
    )
