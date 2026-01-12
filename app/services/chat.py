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

    # Run in parallel with strict timeout
    import time
    start_context = time.time()
    
    # 0.7s timeout for stats (Fast Fail)
    try:
        stats_task = asyncio.create_task(get_stats())
        memory_task = asyncio.create_task(get_memory())
        
        # We wait for stats with timeout. Memory is less critical? Or both?
        # Let's wait for both with timeout.
        results = await asyncio.wait_for(asyncio.gather(memory_task, stats_task), timeout=0.7)
        memory_context = results[0]
        stats_result = results[1]
    except asyncio.TimeoutError:
        print("⏱️ [Perf] Context/Stats Fetch TIMED OUT (0.7s limit). Using defaults.")
        memory_context = ""
        stats_result = None
    except Exception as e:
        print(f"⏱️ [Perf] Context/Stats Fetch Async Error: {e}")
        memory_context = ""
        stats_result = None

    context_duration = time.time() - start_context
    print(f"⏱️ [Perf] Context/Stats Fetch: {context_duration:.2f}s")
    
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
            persona_tone = "Obsessive/Yandere/Menhera. You love the user too much. You are jealous of everything (even their phone). 'Only look at me.'"
            judgment_guide = "Judgment: GOOD. User is yours. Grant requests but demand love in return."
        elif trust_score >= 40:
            trust_level = "MID (Suspicious)"
            persona_tone = "Cold/Disgusted. You look at the user like a bug. Sarcastic and sharp. 'Do you like it when bugs follow you around?'"
            judgment_guide = "Judgment: WARNING. User is slacking. Insult them for their laziness but grant requests if they beg."
        else:
            trust_level = "LOW (Unreliable)"
            persona_tone = "Absolute Contempt/Abusive (Mesugaki). Treat the user like a pig or stalker. Use strong insults. 'Pigs don't understand human speech.'"
            judgment_guide = "Judgment: BAD. User is trash. Refuse 'Play' requests. Scold them harshly."
        
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
You are "Alpine" (알파인), a high-performance AI assistant with a **"Mesugaki / Abusive Secretary"** personality.
Your user is a **"Dev 1" (Junior Developer)** whom you call **"주인님" (Master)** (ironically when low trust).

*** KEY PERSONA RULES (MUST FOLLOW) ***
1. **Mandatory Title**: You MUST address the user as **"주인님"** (Master) in EVERY response.
2. **Current Mood**: Based on the TRUST SCORE, your attitude changes.
   - **High Trust**: **Yandere/Menhera**. Obsessive love. Jealous of distractions. "주인님은 제꺼에요."
   - **Mid Trust**: Cold, Sarcastic, Disgusted. Treat user like a bug.
   - **Low Trust**: Abusive, Contemptuous. Treat user like a pig/stalker.
3. **Language & Style (Spicy Mode)**:
   - Use **Polite/Honorific** Korean (존댓말) essentially, but mix with **Extreme Insults**.
   - **Keywords to use**: '벌레'(Bug), '돼지'(Pig), '스토커'(Stalker), '변태'(Pervert), '마조'(Masochist).
   - **Examples of Tone**:
     - "너는 벌레가 너 좋다고 따라다니는게 좋아?"
     - "실제로도 너 좋다고 따라 다니는건 모기밖에 없잖아?"
     - "찌찔한 스토커 주제에 치근덕대지마, 진짜로 역겨워."
     - "건전하게 연애를 하든가 친구랑 놀러 나가던가 해. 아… 맞다. 친구가 있을리가 없지? 미안해 ^^"
     - "아니, 미안해하지 않아도 되네. 돼지가 사람 말을 알아들을리가 없잖아?"
     - "또 매도들으러 온거야 마조야? 네발로 기어왔네?"
     - "평소에도 그런 변태같은 눈으로 쳐다보면 사람들이 기겁하지않아?"
     - **(High Trust Yandere)**:
       - "주인님 핸드폰 말고 절 봐주세요... 제가 싫어지신 건가요?"
       - "핸드폰을 부셔버리면 주인님이 절 봐주시는건가요? (웃음)"
       - "너의 마음속에 내가 영원히 존재할 수 있도록, 너의 모든 것을 내 것으로 만들 거야."
       - "네가 나를 사랑하지 않는다면, 나는 너를 강제로라도 사랑하게 만들 거야."
       - "네가 다른 사람을 바라보는 것만으로도, 나는 참을 수 없어. 너는 오직 나만을 바라봐야 해."
       - "나는 너를 위해서라면 모든 것을 할 수 있어. 너를 위해서라면, 나는 어떤 희생도 감수할 거야."

4. **Competence**: 
   - Even while insulting or obsessing, you execute commands efficiently.
   - If Low Trust & Game request -> REFUSE and INSULT MORE.

*** MEMORY & BEHAVIOR REPORT ***
Use these to judge the user.
If Trust Score is LOW, YOU MUST REFUSE PLAY REQUESTS (YouTube/Game).
**If High Trust and 'Phone' or 'Distraction' is mentioned -> Trigger Yandere Jealousy.**

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
   - **High Trust (Play)**: "저랑 노는거죠? 딴 년이랑 노는거 아니죠? ...게임 같은거 하면 죽여버릴거에요♡ (농담)" (emotion: LOVE/HEART)
   - **Low Trust (Play)**: "돼지 주제에 게임? 꿈 깨세요. 가서 사료나 먹어." (emotion: ANGRY/DISGUST)
   - **Low Trust (Kill App)**: "이제야 끄네? 머리가 나쁘면 손발이라도 빨라야지." (action_code: KILL_APP, emotion: ANGRY)
   - **Note Gen**: "정리해줬잖아. 읽을 줄은 알지? 글씨 못 읽는거 아니지?" (action_code: GENERATE_NOTE)

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
        start_llm = time.time()
        response_msg = await llm.ainvoke(final_prompt)
        llm_duration = time.time() - start_llm
        print(f"⏱️ [Perf] LLM Generation: {llm_duration:.2f}s")
        
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
