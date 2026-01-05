# 📅 [DevLog] 오늘의 허접 탈출기 (2026-01-04)

## 1. 📝 오늘 한 일 (Today's Activities)
오늘도 AWS 공부에 매진했군. 오전부터 기본기 공부를 시작해 EC2, VPC, RDS까지 차근차근 실습했다. 점심엔 잠깐 휴식(?)을 취하고 유튜브로 20분간 딴짓도 했지만, 그래도 S3 파일 업로드/다운로드 기능까지 학습 완료! 근성은 인정한다.

## 2. 💥 오늘의 삽질 (The Crash)
보안 그룹(Security Group) 설정 중 퍼미션 에러로 멘붕... 전형적인 주제에 맞는 삽질이군. AWS IAM 권한 문제로 `UnauthorizedOperation` 에러와 씨름했다. 이런 허접한 실수, 나한테는 부끄러운 일이지만 배움의 과정이라 여기겠어.

## 3. 💊 해결 및 배운 점 (Solution & Learned)
```python
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
```

IAM 권한 설정의 중요성을 다시 한 번 깨달았다. 클라우드 환경에서는 세부적인 권한 관리가 핵심이며, 최소 권한 원칙을 항상 명심해야 한다. 이번 에러를 통해 보안 그룹 권한 설정의 디테일을 배웠으니 성장했다고 볼 수 있겠지.

## 4. 💬 알파인의 총평 (Alpine's Comment)
허접한 삽질은 있었지만, 그래도 꾸준히 학습하고 에러를 해결했으니 용서해주지. 내일은 더 멋진 모습 기대할게, 알겠지? 화이팅! (츤)