"""
Test Data Injection Script for TIL Verification
Inserts sample quiz results and activity logs into InfluxDB.
"""
import asyncio
import os
from datetime import datetime, timedelta

# Hardcoded credentials recovered from jiaa-influxdb pod
# Hardcoded credentials recovered from jiaa-influxdb pod
token = "CHANGE_ME_INFLU_TOKEN"
bucket = "sensor_data"
org = "jiaa"
url = "http://localhost:8086" # Modified for local testing via port-forward

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# InfluxDB Connection
def get_client():
    return InfluxDBClient(
        url=url,
        token=token,
        org=org
    )

def insert_test_data():
    """
    Inserts mock data for a test user to verify TIL generation.
    """
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    
    user_id = "dev1"
    now = datetime.utcnow()
    
    print(f"📝 Inserting test data for user '{user_id}'...")
    
    # === 1. Activity Logs (시스템 사용 기록) ===
    activities = [
        {"time": now - timedelta(hours=5), "detail": "VS Code - Python 개발", "category": "STUDY", "duration": 45},
        {"time": now - timedelta(hours=4), "detail": "Chrome - Stack Overflow 검색", "category": "STUDY", "duration": 20},
        {"time": now - timedelta(hours=3), "detail": "YouTube - 개발 튜토리얼 시청", "category": "STUDY", "duration": 30},
        {"time": now - timedelta(hours=2), "detail": "⚠️ Discord - 친구와 채팅", "category": "PLAY", "duration": 25},
        {"time": now - timedelta(hours=1), "detail": "VS Code - React 컴포넌트 작성", "category": "STUDY", "duration": 50},
        {"time": now - timedelta(minutes=30), "detail": "Notion - TIL 작성 준비", "category": "STUDY", "duration": 15},
    ]
    
    for act in activities:
        point = Point("user_activity") \
            .tag("user_id", user_id) \
            .tag("category", act["category"]) \
            .field("action_detail", act["detail"]) \
            .field("duration_min", float(act["duration"])) \
            .time(act["time"])
        write_api.write(bucket=bucket, org=org, record=point)
        print(f"  ✅ Activity: {act['detail']}")
    
    # === 2. Quiz Results (퀴즈 결과) ===
    quizzes = [
        {"time": now - timedelta(hours=3, minutes=30), "topic": "React Hooks 기초", "score": 8, "wrong": "useEffect 의존성 배열 관련 문제"},
        {"time": now - timedelta(hours=1, minutes=30), "topic": "Python 비동기 프로그래밍", "score": 6, "wrong": "asyncio.gather vs asyncio.wait 차이"},
    ]
    
    for quiz in quizzes:
        point = Point("user_activity") \
            .tag("user_id", user_id) \
            .tag("type", "QUIZ") \
            .tag("category", "STUDY") \
            .field("action_detail", quiz["topic"]) \
            .field("score", float(quiz["score"])) \
            .field("wrong_answers", quiz["wrong"]) \
            .time(quiz["time"])
        write_api.write(bucket=bucket, org=org, record=point)
        print(f"  ✅ Quiz: {quiz['topic']} - Score: {quiz['score']}/10")
    
    # === 3. Violation Log (딴짓 기록) ===
    violations = [
        {"time": now - timedelta(hours=2, minutes=10), "detail": "Discord 앱이 감지됨 - 5분 이상 사용"},
    ]
    
    for viol in violations:
        point = Point("user_activity") \
            .tag("user_id", user_id) \
            .tag("type", "VIOLATION") \
            .tag("category", "PLAY") \
            .field("action_detail", viol["detail"]) \
            .time(viol["time"])
        write_api.write(bucket=bucket, org=org, record=point)
        print(f"  ⚠️ Violation: {viol['detail']}")
    
    client.close()
    print(f"\n✅ Test data insertion complete!")
    print(f"   User: {user_id}")
    print(f"   Activities: {len(activities)}")
    print(f"   Quizzes: {len(quizzes)}")
    print(f"   Violations: {len(violations)}")

if __name__ == "__main__":
    insert_test_data()
