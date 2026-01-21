"""
이벤트 카운트 테이블을 생성하는 스크립트
실행: python init_event_table.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import get_settings

settings = get_settings()

async def init_tables():
    """데이터베이스 테이블 생성"""
    # 데이터베이스 URL 구성
    database_url = f"postgresql+asyncpg://{settings.PG_USER}:{settings.PG_PASSWORD}@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
    
    # 엔진 생성
    engine = create_async_engine(database_url, echo=False)
    
    # SQL로 직접 테이블 생성 (인덱스 중복 문제 회피)
    create_table_sql = text("""
    CREATE TABLE IF NOT EXISTS event_counts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR NOT NULL,
        event_type VARCHAR NOT NULL,
        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        metadata VARCHAR NULL
    );
    
    CREATE INDEX IF NOT EXISTS ix_event_counts_user_id ON event_counts (user_id);
    CREATE INDEX IF NOT EXISTS ix_event_counts_event_type ON event_counts (event_type);
    CREATE INDEX IF NOT EXISTS ix_event_counts_timestamp ON event_counts (timestamp);
    CREATE INDEX IF NOT EXISTS idx_user_event_time ON event_counts (user_id, event_type, timestamp);
    CREATE INDEX IF NOT EXISTS idx_user_time ON event_counts (user_id, timestamp);
    """)
    
    try:
        async with engine.begin() as conn:
            await conn.execute(create_table_sql)
        print("✅ Event counts table created successfully!")
                
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_tables())
