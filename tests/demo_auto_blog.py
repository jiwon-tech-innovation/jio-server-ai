import asyncio
import sys
import os
from unittest.mock import patch

sys.path.append(".")

# Load .env if present (to ensure credentials work)
from dotenv import load_dotenv
load_dotenv()

# We need to ensure settings are loaded correctly. 
# Instead of mocking, let's trust the environment or set defaults if missing for the demo.
if "BEDROCK_REGION" not in os.environ:
    os.environ["BEDROCK_REGION"] = "us-east-1"
if "PROJECT_NAME" not in os.environ:
    os.environ["PROJECT_NAME"] = "JIAA"

from app.services.review_service import review_service

async def run_demo():
    print("--- [Auto-Blog Demo] Starting Scenario Simulation ---")
    
    # 1. Prepare Mock Data (User Scenario)
    mock_activities = [
        "[10:00] AWS 기본기 공부 시작 (STUDY)",
        "[11:00] EC2 인스턴스 생성 및 VPC 네트워크 구성 실습 (STUDY)",
        "[12:00] 점심 식사 (NEUTRAL)",
        "[13:00] 데이터베이스(RDS) 생성 및 로그인 실습 (STUDY)",
        "[14:00] 유튜브 시청 (PLAY) - 20분간 딴짓함",
        "[15:00] 보안 그룹(Security Group) 설정 중 퍼미션 에러로 멘붕 (STUDY)",
        "[16:00] S3 파일 업로드/다운로드 기능 학습 완료 (STUDY)",
        "[18:00] 저녁 식사 (NEUTRAL)"
    ]
    
    error_log = """
    botocore.exceptions.ClientError: An error occurred (UnauthorizedOperation) when calling the AuthorizeSecurityGroupIngress operation: 
    You are not authorized to perform this operation. User: arn:aws:iam::123456789012:user/Dev1 is not authorized to perform: ec2:AuthorizeSecurityGroupIngress on resource: arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0
    """
    
    solution_code = """
    # IAM 권한 문제 해결:
    # 1. IAM 콘솔 이동 -> 사용자(Dev1) 선택
    # 2. 'AmazonEC2FullAccess' 또는 인라인 정책 추가
    
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "ec2:AuthorizeSecurityGroupIngress",
                "Resource": "*"
            }
        ]
    }
    """

    # 2. Patch Memory Service to return our mock activities
    with patch("app.services.memory_service.memory_service.get_daily_activities", return_value=mock_activities):
        print("--- [Step 1] Fetching Daily Activities (Mocked) ---")
        print(f"Activities found: {len(mock_activities)}")
        
        print("--- [Step 2] Generating Blog Post via LLM (Alpine Persona) ---")
        # We allow the real LLM call here to see the actual creative output!
        # Assuming credentials are set in .env or environment.
        
        try:
            result = await review_service.generate_blog_post(
                error_log=error_log,
                solution_code=solution_code,
                user_id="dev1"
            )
            
            if result['status'] == 'SAVED':
                print(f"\n--- [Success] Blog Saved to: {result['file_path']} ---")
                
                # Read content
                with open(result['file_path'], "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Save to workspace for Antigravity to read
                with open("tests/demo_output.md", "w", encoding="utf-8") as f:
                    f.write(content)
                
                print("\n=== [PREVIEW START] ===\n")
                print(content)
                print("\n=== [PREVIEW END] ===")
            else:
                print(f"--- [Error] Failed to save: {result['message']} ---")
                
        except Exception as e:
            print(f"--- [Critical Error] {e} ---")

if __name__ == "__main__":
    asyncio.run(run_demo())
