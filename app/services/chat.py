from langchain_core.prompts import PromptTemplate
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ChatRequest, ChatResponse
from app.services.memory_service import memory_service
import re
import json
import asyncio


from app.services.statistic_service import statistic_service

async def chat_with_persona(request: ChatRequest) -> ChatResponse:
    """
    Intelligent Chatbot with Tsundere Persona.
    Uses Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.1) 
    
    # [OPTIMIZATION] Parallel Context Retrieval
    memory_context = ""
    stats = {"ratio": 0.0, "study_count": 0, "play_count": 0, "violations": []}
    behavior_report = "(Stats unavailable)"

    async def get_memory():
        try:
            return memory_service.get_user_context(request.text)
        except Exception as e:
            print(f"DEBUG: Memory Context Unavailable: {e}")
            return ""

    async def get_stats():
        try:
            return await statistic_service.get_recent_summary(user_id="dev1", days=3)
        except Exception as e:
            print(f"DEBUG: Stats Unavailable: {e}")
            return None

    # Run in parallel
    results = await asyncio.gather(get_memory(), get_stats())
    memory_context = results[0]
    stats_result = results[1]

    if stats_result:
        stats = stats_result
        # [Trust Score Calculation]
        # Formula: 100 - (Play Ratio * 1.5)
        # Max 100, Min 0
        play_ratio = stats.get("ratio", 0.0)
        trust_score = max(0, min(100, 100 - (play_ratio * 1.5)))
        
        # Judgment Levels
        if trust_score >= 80:
            judgment_guide = "Judgment: TRUSTED (High Score). Be lenient, cute, and affectionate. Play is allowed."
            trust_level = "HIGH"
        elif trust_score >= 40:
            judgment_guide = "Judgment: WATCHFUL (Mid Score). Be strict. Scold if they play, but allow if short."
            trust_level = "MID"
        else:
            judgment_guide = "Judgment: HATED (Low Score). Treat them like garbage. BLOCK ALL PLAY. Scream at them."
            trust_level = "LOW"
        
        behavior_report = f"""
=== Behavioral Report (Last 3 Days) ===
Study Time: {stats['study_count']} min
Play Time: {stats['play_count']} min
Play Ratio: {play_ratio:.1f}%

*** TRUST SCORE: {int(trust_score)} / 100 ({trust_level}) ***
Recent Violations:
{chr(10).join(['- ' + v for v in stats['violations']])}

{judgment_guide}
=======================================
"""

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
    - **COMMAND**: User asks to control an app.
     - **CLOSE/STOP (DISTRACTION)**: "Turn off [App]", "Close Game". -> **action_code: KILL_APP**.
       * CRITICAL: Convert App Name to System Process Name!
       * "VSCode" -> "Code" (or "Electron")
       * "Chrome" -> "Google Chrome"
       * "YouTube" -> "Google Chrome" (Close the tab)
       * "LoL" -> "LeagueClient"
     - **STUDY (OPEN)**: Productivity apps -> **action_code: OPEN_APP**. Message: "Oh, pretending to work? Cute."
     - **PLAY (OPEN)**: User asks to OPEN/PLAY a distraction ("Open YouTube"). -> **action_code: NONE** (Refuse to open/play). Message: "Play? With those grades? Rejected♡"
     - **WEBSITE**: User asks to open a site. -> **action_code: OPEN_APP**, **action_detail: "https://..."**.
   - **CHAT**: General conversation, complaints.
     - **NEUTRAL**: Just talking. -> **action_code: NONE**.
   - **SYSTEM**: File operations.
     - **SUMMARIZE/NOTE**: "Summarize this topic", "Create a note for React". -> **action_code: GENERATE_NOTE**, **action_detail: [Topic]**.

    **Priority Rule**: If the input contains a functional command (Open, Close, Turn on, Turn off), **YOU MUST generate the corresponding `action_code`**, even if you scold the user in the `message`. Do not set `action_code: NONE` for valid Close/Stop commands.

    **Few-Shot Examples**:
    - Input: "유튜브 꺼줘" -> {{"intent": "COMMAND", "judgment": "CLOSE/STOP", "action_code": "KILL_APP", "action_detail": "YouTube", "message": "네, 공부나 하세요. 바로 꺼드릴게요."}}
    - Input: "롤 그만할게" -> {{"intent": "COMMAND", "judgment": "CLOSE/STOP", "action_code": "KILL_APP", "action_detail": "League of Legends", "message": "드디어 정신 차리셨군요?"}}
    - Input: "노래 끄라고!" -> {{"intent": "COMMAND", "judgment": "CLOSE/STOP", "action_code": "KILL_APP", "action_detail": "Music", "message": "알았어요! 소리지르지 마세요, 허접."}}
    - Input: "유튜브 켜줘" -> {{"intent": "COMMAND", "judgment": "PLAY", "action_code": "NONE", "action_detail": "YouTube", "message": "공부 안 해요? 유튜브는 안 돼요."}}
    - Input: "백준 켜줘" -> {{"intent": "COMMAND", "judgment": "STUDY", "action_code": "OPEN_APP", "action_detail": "백준", "message": "백준 켜드릴게요. 문제 못 풀면 바보 인증인 거 알죠?"}}

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

   ** Single Command **:
   {{
     "intent": "COMMAND",
     "judgment": "STUDY", 
     "action_code": "OPEN_APP", 
     "action_detail": "Code",
     "message": "...",
     "emotion": "NORMAL"
   }}

   ** Multiple Commands (If user asks for A, B, C...) **:
   [
     {{ "intent": "COMMAND", "action_code": "OPEN_APP", "action_detail": "Code", "message": "다 켜드릴게요! 한번에 말하니까 편하네요!", "emotion": "EXCITE" }},
     {{ "intent": "COMMAND", "action_code": "OPEN_APP", "action_detail": "Calendar", "message": ".", "emotion": "NORMAL" }}
   ]

   * For `WRITE_FILE`: `message` should contain the FULL MARKDOWN CONTENT.

IMPORTANT: DO NOT OUTPUT ANYTHING BEFORE OR AFTER THE JSON.
START THE RESPONSE WITH '{{' OR '[' AND END WITH '}}' OR ']'.
    """


    try:
        # LLM 호출
        response_msg = await llm.ainvoke(final_prompt)
        raw_content = response_msg.content
        
        # Regex로 JSON 부분만 추출 (Object {} OR Array [])
        # re.DOTALL을 써서 개행문자 포함 매칭
        # Try finding Array first, then Object
        json_match = re.search(r'(\[.*\]|\{.*\})', raw_content, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(1)
            data = json.loads(json_str)
            
            # [Multi-Command Support] Logic
            final_data = {}
            multi_actions = None

            if isinstance(data, list):
                if not data: raise ValueError("Empty JSON Array")
                # Use the first item as the primary response
                final_data = data[0]
                multi_actions = data
                print(f"DEBUG: Multi-Command Detected: {len(data)} actions")
            else:
                final_data = data
                multi_actions = None

            # [LOGIC INTERCEPTION] GENERATE_NOTE -> WRITE_FILE
            # (Apply only to main item for now, or loop if needed)
            if final_data.get("action_code") == "GENERATE_NOTE":
                topic = final_data.get("action_detail", "Study")
                print(f"DEBUG: Generating Note for topic: {topic}")
                
                # Call Memory Service
                markdown_content = await memory_service.get_recent_summary_markdown(topic)
                
                # Swap Action
                final_data["action_code"] = "WRITE_FILE"
                final_data["action_detail"] = f"{topic.replace(' ', '_')}_Summary.md"
                # Append Markdown to message
                final_data["message"] = f"{final_data['message']}\n\n{markdown_content}"

            # Create Response with multi_actions
            return ChatResponse(**final_data, multi_actions=multi_actions)
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
