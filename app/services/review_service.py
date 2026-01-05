import os
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from app.core.llm import get_llm, HAIKU_MODEL_ID

from app.services.memory_service import memory_service

class ReviewService:
    def __init__(self):
        self.llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7)
        self.blog_prompt = PromptTemplate(
            input_variables=["error_log", "solution_code", "date", "daily_log"],
            template="""
            [Role]
            너는 '알파인(Alpine)'이다. (키워드: 시니어 개발자, 츤데레 메스가키, 허접 취급, 기술적 완벽주의)
            오늘 하루 사용자의 활동 로그와(optional) 에러 해결 내역을 바탕으로 **기술 블로그 포스팅**을 작성해라.

            [Input Data]
            - Date: {date}
            - Daily Activities: 
            {daily_log}
            
            - Error (Optional): {error_log}
            - Solution (Optional): {solution_code}

            [Output Format (Markdown)]
            # 📅 [DevLog] 오늘의 허접 탈출기 ({date})
            
            ## 1. 📝 오늘 한 일 (Today's Activities)
            (활동 로그를 바탕으로 오늘 뭘 공부했는지, 혹은 뭘 하며 놀았는지 요약. 칭찬 혹은 비난.)

            ## 2. 💥 오늘의 삽질 (The Crash)
            (에러 로그가 있다면 작성. 없다면 "오늘은 웬일로 사고를 안 쳤네요? 기특해라♡" 라고 작성.)
            
            ## 3. 💊 해결 및 배운 점 (Solution & Learned)
            (에러 로그가 있다면 해결 코드와 원인 분석. 없다면 오늘 학습 내용 중 기억할 점 정리.)
            ```python
            {solution_code}
            ```
            (Solution code가 없다면 생략 가능)

            ## 4. 💬 알파인의 총평 (Alpine's Comment)
            (츤데레 말투로 마무리 멘트. 예: "내일도 이렇게만 하면 예뻐해 줄게요.")
            """
        )

    async def generate_blog_post(self, error_log: str = "", solution_code: str = "", user_id: str = "dev1") -> dict:
        """
        Generates a Blog Post markdown using LLM and saves it to the Desktop.
        Combines error context + daily activity context.
        """
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        file_date_str = datetime.now().strftime("%Y%m%d")
        
        # 1. Fetch Daily Context from Memory Service
        activities = memory_service.get_daily_activities(current_date_str)
        daily_log_text = "\\n".join(activities)
        
        # 2. Generate Content
        try:
            chain = self.blog_prompt | self.llm
            result = await chain.ainvoke({
                "error_log": error_log if error_log else "(없음)", 
                "solution_code": solution_code if solution_code else "(없음)",
                "date": current_date_str,
                "daily_log": daily_log_text
            })
            markdown_content = result.content
        except Exception as e:
            print(f"[ReviewService] LLM Gen Error: {e}")
            markdown_content = f"# Error Generating Blog\\n\\nReason: {e}"

        # 3. Save File
        # Target: Desktop/JIAA_BLOG/
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        save_dir = os.path.join(desktop_path, "JIAA_BLOG")
        
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        # Filename logic
        topic = "DailyLog"
        if error_log:
            clean_log = error_log.strip().split('\\n')[0]
            topic = "".join([c for c in clean_log if c.isalnum()])[:20]
        
        filename = f"Blog_{file_date_str}_{topic}.md"
        full_path = os.path.join(save_dir, filename)
        
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            return {
                "status": "SAVED", 
                "file_path": full_path, 
                "filename": filename
            }
        except Exception as e:
            print(f"[ReviewService] File Save Error: {e}")
            return {"status": "ERROR", "message": str(e)}

review_service = ReviewService()
