from fastapi import FastAPI
from app.core.config import get_settings

settings = get_settings()

from contextlib import asynccontextmanager
from app.services.memory_service import memory_service
from app.core.kafka import kafka_producer


async def run_migrations():
    """
    자동 DB 마이그레이션 - 서버 시작 시 필요한 테이블 생성
    Idempotent: 여러 번 실행해도 안전함
    """
    from sqlalchemy import text, inspect
    from app.core.database import engine, Base
    from app.models.event_count import EventCount
    
    try:
        # SQLAlchemy 메타데이터를 사용하여 테이블 생성 (더 안전함)
        async with engine.begin() as conn:
            # Base.metadata.create_all()을 async로 실행
            await conn.run_sync(Base.metadata.create_all)
        print("✅ [Migration] All tables created via SQLAlchemy metadata")
    except Exception as e:
        print(f"⚠️ [Migration] SQLAlchemy metadata creation failed: {e}")
        # Fallback: 직접 SQL 실행
        try:
            create_table_sql = text("""
            CREATE TABLE IF NOT EXISTS event_counts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                meta_data VARCHAR NULL
            )
            """)
            
            create_index1_sql = text("""
            CREATE INDEX IF NOT EXISTS idx_event_user_time ON event_counts (user_id, timestamp)
            """)
            
            create_index2_sql = text("""
            CREATE INDEX IF NOT EXISTS idx_event_type ON event_counts (event_type, timestamp)
            """)
            
            async with engine.begin() as conn:
                await conn.execute(create_table_sql)
                await conn.execute(create_index1_sql)
                await conn.execute(create_index2_sql)
            print("✅ [Migration] event_counts table created via SQL fallback")
        except Exception as fallback_err:
            print(f"❌ [Migration] Fallback SQL also failed: {fallback_err}")
            # 테이블이 이미 존재할 수도 있으므로 경고만 출력
            import traceback
            print(f"Migration traceback:\n{traceback.format_exc()}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting JIAA Intelligence Worker (HTTP: 8000, gRPC: 50051)...")
    await run_migrations()  # 자동 DB 마이그레이션
    await kafka_producer.start()
    yield
    # Shutdown
    print("Shutting down... Consolidating Memory...")
    try:
        await memory_service.consolidate_memory()
        print("Memory consolidation complete.")
        await kafka_producer.stop()
    except Exception as e:
        print(f"Error during shutdown memory consolidation: {e}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "JIAA Intelligence Worker is running"}

@app.get("/health")
async def health_check():
    """ALB Health Check endpoint (HTTP/1.1 compatible)"""
    return {"status": "healthy"}

from app.api.v1.api import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import asyncio
    import uvicorn
    from app.core.grpc_server import serve_grpc

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)

    async def main():
        await asyncio.gather(
            server.serve(),
            serve_grpc()
        )

    asyncio.run(main())

