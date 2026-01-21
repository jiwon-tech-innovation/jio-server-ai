from datetime import datetime
from app.services.calendar_service import calendar_service
from app.services.statistic_service import statistic_service
from app.services.memory_service import memory_service
from app.core.llm import get_llm, SONNET_MODEL_ID
from langchain_core.prompts import PromptTemplate

class ReportService:
    def __init__(self):
        # [User Request] Use Sonnet for higher quality reports and better Korean support
        self.llm = get_llm(model_id=SONNET_MODEL_ID, temperature=0.7)

    async def generate_daily_wrapped(self, user_id: str) -> str:
        """
        Generates a "Daily Wrapped" report by triangulating Plan vs Actual vs Said.
        """
        # 1. Fetch Plans (Calendar)
        plans = calendar_service.get_todays_plan()
        plan_str = "\n".join([f"- [{p['start']}~{p['end']}] {p['summary']}" for p in plans])
        if not plan_str: plan_str = "(No plans recorded)"

        # 2. Fetch Actuals (InfluxDB Timeline)
        timeline = await statistic_service.get_daily_timeline(user_id)
        actual_str = "\n".join(timeline)
        if not actual_str: actual_str = "(No significant activity logs)"

        # 3. Fetch Said (Vector Memory - Daily Summary)
        # We reuse get_daily_activities from MemoryService, but it searches STM.
        said_list = memory_service.get_daily_activities()
        said_str = "\n".join(said_list)

        # 4. Fetch Quiz Results (Performance) - NOW uses InfluxDB as PRIMARY source
        # InfluxDB is more reliable as it doesn't require auth token forwarding
        quiz_logs = await statistic_service.get_daily_quiz_logs(user_id)
        
        if quiz_logs:
            # Format InfluxDB quiz logs for TIL
            quiz_list = [
                f"- {q.get('topic', 'Unknown')}: Score {q.get('score', 0)}"
                for q in quiz_logs
            ]
        else:
            # Fallback 1: Try jiaa-auth API (requires auth token)
            from app.services.quiz_service import quiz_service
            quiz_list = await quiz_service.get_daily_quiz_results(user_id)
            
            # Fallback 2: Try memory_service (Vector DB)
            if not quiz_list:
                quiz_list = memory_service.get_daily_quiz_results()
        
        quiz_str = "\n".join(quiz_list) if quiz_list else "(No quizzes taken)"

        # 5. LLM Generation (Korean Prompt for Korean Output)
        prompt = f"""
당신은 "알파인", 날카로운 코드 리뷰어이자 라이프 코치입니다.
사용자 "Dev 1"의 "오늘의 회고록"을 작성해주세요.

### 📊 데이터 소스
1. [계획] 오늘 계획했던 것 (캘린더):
{plan_str}

2. [실제] 실제로 한 일 (시스템 로그):
{actual_str}

3. [대화] 사용자가 말한 것 (채팅 기록):
{said_str}

4. [성과] 퀴즈 점수:
{quiz_str}

### 📝 작성 지침
- **삼위일체 분석**: [계획] vs [실제] vs [성과]를 비교하세요.
- **팩트 체크**:
  - 공부한다고 해놓고 게임했나? ([계획] vs [실제])
  - 열심히 했다고 하면서 퀴즈 점수는 낮나? ([대화] vs [성과]) → "입만 살았군요."
- **톤**: 날카롭고, 분석적이며, 위트있게. 약간 츤데레지만 팩트 기반.
- **포맷**: 마크다운.

### 📋 출력 형식
# 📅 데일리 리포트 ({datetime.now().strftime("%Y-%m-%d")})

## 📊 오늘의 평가
- **등급**: (A/B/C/F)
- **신뢰도 변화**: (오늘 행동 기반)

## 🔍 계획 vs 현실
| 계획 | 실제 | 판정 |
|------|------|------|
| (계획 항목) | (실제 로그) | (통과/탈락) |

## 📉 퀴즈 성과 리뷰
- (퀴즈 점수와 활동 비교 코멘트)
- (틀린 문제 분석 및 조언)

## 🤥 거짓말 탐지기
- ([대화]와 [실제]가 일치했나?)

## 🚀 내일을 위한 액션 아이템
- (구체적인 조언)
"""
        response = await self.llm.ainvoke(prompt)
        return response.content

report_service = ReportService()
