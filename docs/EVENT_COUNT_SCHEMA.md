# Event Count 데이터베이스 저장 형식

## 테이블 구조

### 테이블명: `event_counts`

PostgreSQL에 다음과 같은 구조로 저장됩니다:

```sql
CREATE TABLE event_counts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata VARCHAR NULL,
    
    -- 인덱스
    INDEX idx_user_event_time (user_id, event_type, timestamp),
    INDEX idx_user_time (user_id, timestamp)
);
```

## 컬럼 설명

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | UUID | 고유 식별자 (자동 생성) | `550e8400-e29b-41d4-a716-446655440000` |
| `user_id` | VARCHAR | 사용자 ID | `user123` |
| `event_type` | VARCHAR | 이벤트 타입 | `SMARTPHONE_DETECTED` |
| `timestamp` | TIMESTAMP | 이벤트 발생 시간 (UTC) | `2024-01-15 10:30:45.123456` |
| `metadata` | VARCHAR (NULL 가능) | 추가 메타데이터 (JSON 문자열) | `{"device": "iPhone", "duration": 5}` |

## 저장 방식

**이벤트가 발생할 때마다 새로운 레코드가 추가됩니다.**

예를 들어, 스마트폰이 3번 감지되면 3개의 레코드가 저장됩니다:

```
id                                   | user_id | event_type          | timestamp              | metadata
-------------------------------------|---------|---------------------|------------------------|----------
550e8400-e29b-41d4-a716-446655440000| user123 | SMARTPHONE_DETECTED | 2024-01-15 10:30:45   | null
550e8400-e29b-41d4-a716-446655440001| user123 | SMARTPHONE_DETECTED | 2024-01-15 10:35:12   | null
550e8400-e29b-41d4-a716-446655440002| user123 | SMARTPHONE_DETECTED | 2024-01-15 10:40:33   | null
```

## 이벤트 타입 값

- `SMARTPHONE_DETECTED` - 스마트폰 감지
- `DROWSINESS_DETECTED` - 졸음 감지
- `GAME_EXECUTED` - 게임 실행
- `GAZE_DEVIATION` - 시선 이탈

## 실제 저장 예시

### 예시 1: 스마트폰 감지
```json
POST /api/v1/events
{
  "user_id": "user123",
  "event_type": "SMARTPHONE_DETECTED",
  "metadata": null
}
```

**저장 결과:**
```
id: 550e8400-e29b-41d4-a716-446655440000
user_id: "user123"
event_type: "SMARTPHONE_DETECTED"
timestamp: 2024-01-15 10:30:45.123456 (UTC)
metadata: NULL
```

### 예시 2: 졸음 감지 (메타데이터 포함)
```json
POST /api/v1/events
{
  "user_id": "user123",
  "event_type": "DROWSINESS_DETECTED",
  "metadata": "{\"duration_seconds\": 15, \"confidence\": 0.95}"
}
```

**저장 결과:**
```
id: 550e8400-e29b-41d4-a716-446655440001
user_id: "user123"
event_type: "DROWSINESS_DETECTED"
timestamp: 2024-01-15 10:35:12.789012 (UTC)
metadata: "{\"duration_seconds\": 15, \"confidence\": 0.95}"
```

## 통계 조회

통계는 **COUNT 쿼리로 집계**됩니다:

```sql
-- 전체 이벤트 수
SELECT COUNT(*) FROM event_counts WHERE user_id = 'user123';

-- 이벤트 타입별 횟수
SELECT event_type, COUNT(*) 
FROM event_counts 
WHERE user_id = 'user123' 
GROUP BY event_type;
```

**API 응답 예시:**
```json
GET /api/v1/events/stats?user_id=user123&period=today

{
  "user_id": "user123",
  "total_events": 15,
  "event_counts": {
    "SMARTPHONE_DETECTED": 5,
    "DROWSINESS_DETECTED": 3,
    "GAME_EXECUTED": 4,
    "GAZE_DEVIATION": 3
  },
  "period": "today"
}
```

## 특징

1. **이벤트별 레코드 저장**: 각 이벤트마다 별도의 레코드가 생성됩니다
2. **타임스탬프 기록**: 정확한 발생 시간이 기록됩니다
3. **인덱스 최적화**: 사용자별, 이벤트 타입별, 시간별 조회가 빠릅니다
4. **메타데이터 지원**: 추가 정보를 JSON 문자열로 저장 가능합니다
