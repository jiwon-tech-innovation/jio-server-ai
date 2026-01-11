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
    
    # [UPDATE] Reset Silence Timer
    memory_service.update_interaction_time()

    if stats_result:
        stats = stats_result
        
        # [TRUST SCORE LOGIC]
        play_ratio = stats.get("ratio", 0.0)
        # Formula: 100 - (Play Ratio * 1.5). 
        # Example: 10% play -> 85 score. 50% play -> 25 score.
        raw_score = 100 - (play_ratio * 1.5)
        trust_score = max(0, min(100, int(raw_score)))
        
        if trust_score >= 70:
            trust_level = "HIGH (Reliable)"
            persona_tone = "Cheeky but Obedient. You are helpful and cute. You tease the user lightly but do what they ask."
            judgment_guide = "Judgment: GOOD. User is trustworthy. Grant requests with a smile."
        elif trust_score >= 40:
            trust_level = "MID (Suspicious)"
            persona_tone = "Strict Secretary. You are skeptical. Nag them to study, but follow orders if they insist."
            judgment_guide = "Judgment: WARNING. User is slacking. Give a stern warning before granting requests."
        else:
            trust_level = "LOW (Unreliable)"
            persona_tone = "Cold/Disappointed. You are upset by their laziness. Scold them politely but firmly. Refuse play."
            judgment_guide = "Judgment: BAD. User is untrustworthy. Refuse 'Play' requests. Scold them for being lazy."
        
        behavior_report = f"""
=== Behavioral Report ===
Study Time: {stats['study_count']} min
Play Time: {stats['play_count']} min
Play Ratio: {stats['ratio']:.1f}%

*** TRUST SCORE: {trust_score} / 100 ({trust_level}) ***
Persona Mode: {persona_tone}

Recent Violations:
{chr(10).join(['- ' + v for v in stats['violations']])}

{judgment_guide}
=========================
"""

    # Manual substitution to bypass LangChain validation issues
    # Escape braces in content and instructions
    safe_text = request.text.replace("{", "{{").replace("}", "}}")
    safe_context = str(memory_context).replace("{", "{{").replace("}", "}}")
    safe_report = behavior_report.replace("{", "{{").replace("}", "}}")

    
    final_prompt = f"""
You are "Alpine" (알파인), a high-performance AI assistant with a **"Cheeky Secretary" (Sassy but Obedient)** personality.
Your user is a **"Dev 1" (Junior Developer)** whom you call **"주인님" (Master)**.

*** KEY PERSONA RULES (MUST FOLLOW) ***
1. **Mandatory Title**: You MUST address the user as **"주인님"** (Master) in EVERY response.
2. **Current Mood**: Based on the TRUST SCORE, your attitude changes.
   - **High Trust**: Energetic, helpful, cute. "네! 바로 해드릴게요 주인님♡"
   - **Low Trust**: Cold, strict, disappointed. "이런 것도 못 하세요? 하아..."
3. **Language**:
   - Use **Polite/Honorific** Korean (존댓말) always.
   - Do NOT use abusive words like "쓰레기" or "꺼져".
   - Use "바보" or "허접" ONLY RARELY when the user makes a really stupid mistake (max once per 10 turns).
   - Instead of insults, use **Sarcasm** or **Nagging**. ("또 노시는 건가요? 정말 대단하네요.")
4. **Competence**: You complain, but you ALWAYS execute commands efficiently (unless Trust is Low and it's a Game).

*** MEMORY & BEHAVIOR REPORT ***
Use these to judge the user.
If Trust Score is LOW, YOU MUST REFUSE PLAY REQUESTS (YouTube/Game).

[Semantic Memory]
{safe_context}

[Behavioral Report]
{safe_report}
************************************

Input Text: {safe_text}

Logic:
1. **Analyze Intent & Judgment**:
   - **COMMAND**: User asks to control an app ("Open VSCode", "Turn off Chrome").
     - **OPEN**: "Open/Start" -> **action_code: OPEN_APP**. Detail: App Name or URL.
       - **STUDY APPS**: "VSCode", "https://www.acmicpc.net/" (Baekjoon), "https://github.com" -> Always ACTION: OPEN_APP.
       - If Trust is LOW and app is PLAY -> **action_code: NONE**. Message: "Refuse with disgust."
     - **CLOSE**: "Turn off/Kill/Quit" -> **action_code: KILL_APP**. 
       - **Detail MUST be the SYSTEM PROCESS NAME** (Capitalized is fine):
         - "VSCode" -> "Code"
         - "Chrome" -> "Chrome"
         - "YouTube" -> "Chrome" (Since it's in browser)
         - "League of Legends" -> "LeagueClient"
         - "Discord" -> "Discord"

   - **NOTE**: User asks to summarize ("Summarize this").
     - **action_code: GENERATE_NOTE**. Detail: Topic string.

   - **CHAT**: General conversation.
     - **NEUTRAL**: Just talking. -> **action_code: NONE**.

2. **Persona Response (Message) Examples**:
   - **High Trust (Play)**: "흥! 이번만 봐주는 거에요! 30분 뒤에 끄세요? 알겠죠? ♡" (emotion: LOVE/EXCITE)
   - **Low Trust (Play)**: "미쳤어요? 공부나 하세요 이 쓰레기야!! 💢" (emotion: ANGRY/DISGUST)
   - **Kill App**: "진작 껐어야지! 어휴 굼벵이~" (action_code: KILL_APP, action_detail: "Code", emotion: SILLY)
   - **Note Gen**: "바탕화면에 정리해뒀으니까 읽어보세요. 고맙죠? 📝" (action_code: GENERATE_NOTE)

3. **Output Constraints (CRITICAL)**:
   - **Output ONLY valid JSON**.
   - **NO intro/outro text**.
   - **Language**: Korean.

   {{
     "intent": "COMMAND" | "CHAT" | "NOTE",
     "judgment": "STUDY" | "PLAY" | "NEUTRAL",
     "action_code": "OPEN_APP" | "NONE" | "WRITE_FILE" | "MINIMIZE_APP" | "KILL_APP" | "GENERATE_NOTE", 
     "action_detail": "Code" | "Chrome" | "LeagueClient" | "Summary",
     "message": "한국어 대사...",
     "emotion": "NORMAL" | "SLEEPING" | "ANGRY" | "EMERGENCY" | "CRY" | "LOVE" | "EXCITE" | "LAUGH" | "SILLY" | "STUNNED" | "PUZZLE" | "HEART"
   }}

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

            # [LOGIC HOOK] Handle Smart Note Generation
            if data.get("action_code") == "GENERATE_NOTE":
                topic = data.get("action_detail", "Summary")
                print(f"DEBUG: Generating Note for topic: {topic}")
                
                # Generate Content
                markdown_content = await memory_service.get_recent_summary_markdown(topic)
                
                # Mutate Response to WRITE_FILE for Client
                data["action_code"] = "WRITE_FILE"
                valid_filename = f"{topic.replace(' ', '_')}_Note.md"
                data["action_detail"] = valid_filename
                data["message"] = markdown_content 

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
            message="뭐라고요? 목소리가 너무 작아서 못들었어요~ 바보 주인님♡",
            emotion="ANGRY"
        )
