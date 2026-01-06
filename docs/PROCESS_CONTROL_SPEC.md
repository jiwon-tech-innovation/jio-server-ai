# Dev 5 프로세스 제어 기능 명세서 (Process Control Specification)

## 개요 (Overview)
Dev 5 (Server AI)는 사용자의 음성 명령을 분석하여 Dev 1 (OS Agent)이 실행할 구체적인 프로세스 제어 명령(JSON)을 생성하는 역할을 수행합니다.

- **역할**: "Brain" (판단 및 명령 생성)
- **실행 주체**: Dev 1 (실제 OS 명령 수행)
- **통신 방식**: gRPC (AudioService.TranscribeAudio 응답의 `intent` 필드)

---

## 데이터 흐름 (Data Flow)

### Input (Dev 1 -> Dev 5)
- **사용자의 음성 스트림** ([AudioRequest](../app/protos/audio.proto))
- **(Optional) 현재 실행 중인 미디어 정보**

### Processing (Dev 5 내부)
1. **STT**: 음성을 텍스트로 변환 ("유튜브 꺼줘")
2. **Context Fetch**: (병렬) 사용자의 행동 내역(InfluxDB) 및 기억(VectorDB) 조회
3. **LLM Decision**: 페르소나(Mesugaki)에 기반하여 판단(Judgment) 및 행동(Action) 결정

### Output (Dev 5 -> Dev 1)
- [AudioResponse](../app/protos/audio.proto)의 `intent` 필드에 JSON 문자열로 명령 전달.

---

## 명령 프로토콜 (Command Protocol)
Dev 1에게 전달되는 JSON intent의 구조와 정의입니다.

### 3.1 JSON 구조
```json
{
  "text": "공부 안하고 유튜브를 봐? 당장 끕니다! 💢",  // AI의 음성 대사
  "state": "PLAY",                                // 현재 상황 판단 (STUDY / PLAY / NEUTRAL)
  "type": "COMMAND",                              // 의도 유형 (COMMAND / CHAT)
  "command": "KILL_APP",                          // 구체적인 행동 코드
  "parameter": "YouTube",                         // 행동 대상 (App Name or Process Name)
  "emotion": "ANGRY"                              // AI 표정 태그
}
```

### 3.2 행동 코드 (Action Codes)
현재 [chat.py](../app/services/chat.py) 프롬프트에 구현되어 있는 코드 목록입니다.

| 코드 | 설명 | 트리거 예시 | 상태 |
| :--- | :--- | :--- | :--- |
| **OPEN_APP** | 특정 애플리케이션 실행 | "VSCode 켜줘", "노래 틀어줘" | ✅ 구현 완료 |
| **KILL_APP** | 실행 중인 앱 강제 종료 | "유튜브 꺼", "롤 꺼" (또는 AI가 딴짓 판단 시) | ✅ 구현 완료 |
| **MINIMIZE_APP** | 창 최소화 (바탕화면 보내기) | "롤 켜면 혼난다" (경고성 조치) | ✅ 구현 완료 |
| **WRITE_FILE** | 파일 생성/작성 (코딩) | "요약 파일 만들어줘" | ✅ 구현 완료 |
| **NONE** | 아무 작업 안 함 (단순 대화) | "안녕", "힘들어" | ✅ 구현 완료 |

---

## 판단 로직 (Decision Logic)
단순히 명령을 따르는 것이 아니라, 사용자의 행동 패턴(Behavior Stats)에 따라 거절하거나 강제로 종료할 수 있습니다.

### 시나리오 A: 공부 모드일 때 딴짓 (유튜브)
- **User**: "유튜브 좀 볼래."
- **Stats**: 최근 노는 시간이 50% 초과 (BAD 상태)
- **AI 판단**: `state: PLAY`, `command: NONE` (거절) 또는 `KILL_APP` (이미 켜져 있다면)
- **Response**: "지금 성적이 바닥인데 유튜브요? 어림도 없어요! 💢"

### 시나리오 B: 생산성 도구 실행
- **User**: "VSCode 켜줘."
- **AI 판단**: `state: STUDY`, `command: OPEN_APP`, `parameter: VSCode`
- **Response**: "흥, 이제야 일하시게요? 잽싸게 대령했습니다. ⭐"

---

## 현재 구현 상태 (Current Status)
- **LLM 프롬프트** ([chat.py](../app/services/chat.py)): 상기 행동 코드(`OPEN_APP`, `KILL_APP`, `MINIMIZE_APP`)를 상황에 맞춰 선택하도록 학습 완료.
- **gRPC 서버** ([grpc_server.py](../app/core/grpc_server.py)): LLM의 응답을 파싱하여 정해진 JSON 스키마로 변환 후 Dev 1에게 반환하는 로직 구현 완료.
- **Kafka 연동**: COMMAND 발생 시 해당 판단 결과를 Dev 4(Core)로도 비동기 전송하여 기록/분석하도록 연동 완료.

**결론**: Dev 5 측면에서의 프로세스 제어 "두뇌" 구현은 100% 완료되었습니다. 실제 프로세스 종료/실행은 이 JSON을 받은 Dev 1이 해당 코드를 처리하는 로직에 달려 있습니다.
