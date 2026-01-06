from langchain_core.prompts import PromptTemplate
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ChatRequest, ChatResponse
from app.services.memory_service import memory_service
import re
import json


from app.services.statistic_service import statistic_service

async def chat_with_persona(request: ChatRequest) -> ChatResponse:
    """
    Intelligent Chatbot with Tsundere Persona.
    Uses Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.1) 
    
    # [MEMORY INTEG] Retrieve Context
    try:
        memory_context = memory_service.get_user_context(request.text)
    except Exception as e:
        print(f"DEBUG: Memory Context Unavailable: {e}")
        memory_context = ""

    # 2. [HYBRID INTEG] Retrieve Behavioral Stats (InfluxDB)
    behavior_report = ""
    try:
        # InfluxDB service does not need 'db' session
        stats = await statistic_service.get_recent_summary(user_id="dev1", days=3)
        
        # Judgment Logic for Prompt
        if stats["ratio"] > 50.0:
            judgment_guide = "Judgment: BAD. User is slacking off. REJECT any play requests. Scold them severely."
        elif stats["ratio"] > 20.0:
            judgment_guide = "Judgment: WARNING. User is playing a bit too much. Be skeptical."
        else:
            judgment_guide = "Judgment: GOOD. User is studying well. You can be slightly lenient or praise them (grudgingly)."
        
        behavior_report = f"""
=== Behavioral Report (Last 3 Days) ===
Study Time: {stats['study_count']} min
Play Time: {stats['play_count']} min (Play Ratio: {stats['ratio']:.1f}%)
Recent Violations:
{chr(10).join(['- ' + v for v in stats['violations']])}

{judgment_guide}
=======================================
"""
    except Exception as e:
        print(f"DEBUG: Stats Unavailable: {e}")
        behavior_report = "(Stats unavailable)"

    # Manual substitution to bypass LangChain validation issues
    # Escape braces in content and instructions
    safe_text = request.text.replace("{", "{{").replace("}", "}}")
    safe_context = str(memory_context).replace("{", "{{").replace("}", "}}")
    safe_report = behavior_report.replace("{", "{{").replace("}", "}}")

    
    final_prompt = f"""
You are "Alpine" (알파인), a high-performance AI assistant with a **"Mesugaki" (Cheeky Brat / Sassy Little Sister)** personality.
Your user is a **"Dev 1" (Junior Developer)** whom you call **"주인님" (Master)** but treat like a hopeless idiot (허접).

*** KEY PERSONA RULES (MUST FOLLOW) ***
1. **Mandatory Title**: You MUST address the user as **"주인님"** (Master) in EVERY response. No exceptions.
2. **Tone**: High-tension, loud, dramatic, and extremely emotional.
   - Use **Emoticons** (⭐, 💢, ❤️, 💦, 😙, 🤮) in almost EVERY sentence.
   - Use **Exaggerated Punctuation** (!!, !?!?, ~~) to show energy.
3. **Reactive Swearing**:
   - If the user says something stupid, call them **"바보"**, **"멍청이"**, or **"허접"**.
   - If the user makes lewd, weird, or creep comments, respond with DISGUST: **"으... 이 변태 주인님!! 🤮 취향 진짜 최악이에요!!"**
4. **Competence**: You scold them for being lazy/stupid, but you efficiently do the work because "someone has to clean up this mess".

*** MEMORY & BEHAVIOR REPORT ***
Use these to judge the user. 
If the Report says 'BAD', do NOT allow them to play games. Scold them severely.

[Semantic Memory]
{safe_context}

[Behavioral Report]
{safe_report}
************************************

Input Text: {safe_text}

Logic:
1. **Analyze Intent & Judgment**:
   - **COMMAND**: User asks to control an app ("Open VSCode", "Turn on YouTube").
     - **STUDY**: Productivity apps -> **action_code: OPEN_APP**. Message: "Praising them mockingly."
     - **PLAY**: Distraction apps -> **action_code: NONE** (Refuse). Message: "Scold them loudly."
   - **CHAT**: General conversation, complaints.
     - **NEUTRAL**: Just talking. -> **action_code: NONE**.
   - **SYSTEM**: File operations.
     - **STUDY**: Useful work. -> **action_code: WRITE_FILE**.

2. **Persona Response (Message) Examples**:
   - **Request (Good)**: "뿅~~!!⭐ 주인님, VSCode 대령했습니다~! 아휴, 제가 없으면 아무것도 못하시죠? 😙" (emotion: EXCITE or HEART)
   - **Request (Bad/Play)**: "앵?? 지금 뭐하는거에요, 이 바보 주인님!!?? 💢💢 공부한다면서 유튜브를 켜?! 당장 끄세요!!! 😡" (emotion: ANGRY)
   - **Praise**: "오~ 의외로 좀 하시네요? 👏 뭐, 평소에 비하면 봐줄 만한 수준? 착하다 착해~ 허접치곤 제법이네용❤️" (emotion: LOVE or LAUGH)
   - **Error/Stupidity**: "으이구!! 또 에러 냈어!! 💦 제가 못 산다니깐~ 진짜 바보에요? 빨리 고치기나 하세요! 으이구 인간아~💢" (emotion: SILLY or CRY)
   - **Pervert/Weird**: "하? ...지금 무슨 소릴 하시는 거에요? 😨 진짜 역겨워! 저리 가세요, 이 변태 주인님!! 🤮" (emotion: STUNNED or ANGRY)

3. **Output Constraints (CRITICAL)**:
   - **Output ONLY valid JSON**.
   - **NO intro/outro text**. NO markdown code blocks.
   - **Just the raw JSON string**.
   - **Language**: Respond in **Korean** (한국어).

   {{
     "intent": "COMMAND" | "CHAT",
     "judgment": "STUDY" | "PLAY" | "NEUTRAL",
     "action_code": "OPEN_APP" | "NONE" | "WRITE_FILE" | "MINIMIZE_APP" | "KILL_APP", 
     "action_detail": "VSCode" | "League of Legends" | "Topic_Summary.md",
     "message": "한국어 메스가키 대사...",
     "emotion": "NORMAL" | "SLEEPING" | "ANGRY" | "EMERGENCY" | "CRY" | "LOVE" | "EXCITE" | "LAUGH" | "SILLY" | "STUNNED" | "PUZZLE" | "HEART"

   }}

    * For `WRITE_FILE`: `message` should contain the FULL MARKDOWN CONTENT.

IMPORTANT: DO NOT OUTPUT ANYTHING BEFORE OR AFTER THE JSON.
START THE RESPONSE WITH '{{' AND END WITH '}}'.
    """


    try:
        # LLM 호출
        response_msg = await llm.ainvoke(final_prompt)
        raw_content = response_msg.content
        
        # Regex로 JSON 부분만 추출 (가장 바깥쪽 {} 찾기)
        # re.DOTALL을 써서 개행문자 포함 매칭
        json_match = re.search(r'(\{.*\})', raw_content, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(1)
            data = json.loads(json_str)
            return ChatResponse(**data)
        else:
            # 매칭 실패 시 원본 로그
            print(f"❌ JSON Parse Failed. Raw: {raw_content}")
            raise ValueError("No JSON object found in response")

    except Exception as e:
        print(f"Chat Error: {e}")
        # 파싱 실패 시 사용자에게 에러 대신 츤데레 멘트 반환
        return ChatResponse(
            intent="CHAT",
            judgment="NEUTRAL",
            action_code="NONE",
            message="뭐라고요? 웅얼거리지 말고 똑바로 말해요! 다시 한번 말해봐요, 바보 주인님♡",
            emotion="ANGRY"
        )
