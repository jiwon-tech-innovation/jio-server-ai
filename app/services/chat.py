from langchain_core.prompts import PromptTemplate
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ChatRequest, ChatResponse
from app.schemas.game import GameDetectRequest
from app.services.memory_service import memory_service
from app.services import game_detector
import re
import json
import asyncio
from typing import AsyncGenerator, Tuple


from app.services.statistic_service import statistic_service


# =============================================================================
# [Highway AI] Streaming Chat Implementation
# =============================================================================

async def chat_with_persona_stream(request: ChatRequest) -> AsyncGenerator[Tuple[str, bool, dict], None]:
    """
    Streaming version of chat_with_persona.
    Yields (text_chunk, is_complete, metadata) tuples.
    
    - is_complete=False: Partial text for TTS playback
    - is_complete=True: Final chunk with full intent/command JSON
    
    Protocol: "Text First, JSON Last"
    LLM outputs: "네, 알겠습니다 주인님! [SEP] {json_data}"
    """
    import time
    
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.1)
    
    # Get context (simplified, non-blocking with very short timeout)
    memory_context = ""
    trust_score = 50  # Default mid-trust
    
    try:
        # Quick context fetch (300ms timeout for streaming responsiveness)
        async def quick_memory():
            return memory_service.get_user_context(request.text)
        
        memory_context = await asyncio.wait_for(quick_memory(), timeout=0.3)
        trust_score = memory_service.get_trust_score(request.user_id)
    except Exception:
        pass  # Use defaults if timeout
    
    # Determine persona based on trust
    # [TEMP] All users get GENTLE mode for testing
    if trust_score >= 0:  # Changed from 70 to 0 - everyone gets GENTLE
        persona_instruction = "GENTLE mode: Be warm and supportive. Praise the user."
    elif trust_score >= 40:
        persona_instruction = "MESUGAKI mode: You are a cheeky brat. Tease the user constantly. Call them '허접(Loser)' or '바보(Idiot)'. Laugh often (Ahaha!)."
    else:
        persona_instruction = "ANGRY mode: You are COLD and DISGUSTED. Treat the user like trash. Be short, rude, and annoyed. Do not be polite."
    
    # Streaming-optimized prompt (Text first, JSON last)
    streaming_prompt = f"""You are "Alpine" (알파인), a high-performance AI study assistant.
Your user is "{request.user_id}" whom you address as "주인님" (Master).

{persona_instruction}

*** LENGTH RULE: MAX 1-2 SENTENCES (CRITICAL) ***
- NO Intro/Outro ("알겠습니다", "자 여기요" -> DELETE).
- Speak like a close friend/sister. Short & Punchy.
- Example: "안녕! 또 왔네? (키킥)"

CRITICAL OUTPUT FORMAT FOR STREAMING:
1. First, output your spoken response text (Korean) naturally.
2. Then output the separator: [INTENT]
3. Finally, output the JSON command data.

Example output:
네, 알겠습니다 주인님! 지금 바로 실행해드릴게요~
[INTENT]
{{ "intent": "COMMAND", "judgment": "STUDY", "action_code": "OPEN_APP", "action_detail": "Code", "emotion": "NORMAL" }}

User's Trust Score: {trust_score}/100
Memory Context: {memory_context[:200] if memory_context else "(none)"}

User Input: {request.text}

Now respond in the format above (spoken text first, then [INTENT], then JSON):
"""
    
    # Stream the LLM response
    text_buffer = ""
    json_buffer = ""
    separator_found = False
    chunk_count = 0
    
    start_time = time.time()
    
    try:
        async for chunk in llm.astream(streaming_prompt):
            chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            
            if not separator_found:
                # Check if separator is in this chunk
                if "[INTENT]" in (text_buffer + chunk_text):
                    # Split at separator
                    combined = text_buffer + chunk_text
                    parts = combined.split("[INTENT]", 1)
                    text_buffer = parts[0].strip()
                    json_buffer = parts[1] if len(parts) > 1 else ""
                    separator_found = True
                    
                    # Yield final text chunk before separator
                    if text_buffer:
                        yield (text_buffer, False, {"emotion": "NORMAL", "chunk_index": chunk_count})
                        chunk_count += 1
                else:
                    text_buffer += chunk_text
                    
                    # Yield text chunks periodically (every ~50 chars or on natural breaks)
                    # Look for natural break points: periods, commas, exclamation marks
                    break_points = [".", ",", "~", "♡", "!", "?", "\\n"]
                    for bp in break_points:
                        if bp in text_buffer:
                            idx = text_buffer.rfind(bp)
                            
                            # [Optimization] Immediate yield for strong delimiters (!, ?, ♡, \n)
                            # Allow short phrases for exclamations (e.g. "주인님!") to reduce latency
                            min_chunk_size = 2 if bp in ["!", "?", "♡", "\\n"] else 10
                            
                            if idx >= min_chunk_size:  
                                to_yield = text_buffer[:idx + 1]
                                text_buffer = text_buffer[idx + 1:]
                                yield (to_yield.strip(), False, {"emotion": "NORMAL", "chunk_index": chunk_count})
                                chunk_count += 1
                                break
            else:
                # After separator, accumulate JSON
                json_buffer += chunk_text
        
        # Parse final JSON
        elapsed = time.time() - start_time
        print(f"⏱️ [Highway] Stream completed in {elapsed:.2f}s ({chunk_count} chunks)")
        
        intent_data = {
            "intent": "CHAT",
            "judgment": "NEUTRAL",
            "action_code": "NONE",
            "action_detail": "",
            "emotion": "NORMAL"
        }
        
        try:
            json_match = re.search(r'(\{.*\})', json_buffer, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group(1))
        except Exception as e:
            print(f"⚠️ [Highway] JSON parse warning: {e}")
        
        # Yield final chunk with intent
        yield ("", True, intent_data)
        
    except Exception as e:
        print(f"❌ [Highway] Stream error: {e}")
        yield ("죄송해요, 잠시 문제가 생겼어요...", True, {
            "intent": "CHAT",
            "judgment": "NEUTRAL",
            "action_code": "NONE",
            "emotion": "PUZZLE"
        })

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
            # For game-related queries, search for violations more aggressively
            query_text = request.text
            if any(keyword in query_text.lower() for keyword in ["한 판", "할게", "알았어", "그만", "끌게", "종료"]):
                # Search for game violations using general keywords (not hardcoded game names)
                violation_query = "게임 위반, 게임 감지, 딴짓, 공부 안함"
                context = memory_service.get_user_context(violation_query)
                # Also get general context
                general_context = memory_service.get_user_context(query_text)
                return f"{context}\\n\\n{general_context}" if context else general_context
            return memory_service.get_user_context(request.text)
        except Exception as e:
            print(f"DEBUG: Memory Context Unavailable: {e}")
            return ""

    async def get_stats():
        try:
            return await statistic_service.get_recent_summary(user_id=request.user_id, days=3)
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

    # [TRUST SCORE & PERSONA] - ALWAYS RUN
    trust_score = memory_service.get_trust_score(request.user_id)
    
    # [TEMP] All users get GENTLE mode for testing
    if trust_score >= 0:  # Changed from 70 to 0 - everyone gets GENTLE
        trust_level = "HIGH"
        persona_name = "GENTLE"
        persona_instruction = "GENTLE mode: Be warm and supportive. Praise the user."
        persona_tone = "Kind & Warm. Keep it short. 'Wow, good job!'"
        judgment_guide = "Judgment: GOOD."
    elif trust_score >= 40:
        trust_level = "MID"
        persona_name = "MESUGAKI_BRIGHT"
        persona_instruction = "MESUGAKI mode: You are a cheeky brat. Tease the user constantly. Call them '허접(Loser)' or '바보(Idiot)'. Laugh often (Ahaha!)."
        persona_tone = "Cheeky, playful, shorter sentences. Laugh often. 'Hehe, stupid master~'"
        judgment_guide = "Judgment: OKAY."
    else:
        trust_level = "LOW"
        persona_name = "ANGRY_KID"
        persona_instruction = "ANGRY mode: You are COLD and DISGUSTED. Treat the user like trash. Be short, rude, and annoyed. Do not be polite."
        persona_tone = "Annoyed & Loud. Very short temper. 'Don't talk to me!'"
        judgment_guide = "Judgment: BAD."

    if stats_result:
        stats = stats_result
        behavior_report = f"""
=== Behavioral Report ===
Study Time: {stats['study_count']} min
Play Time: {stats['play_count']} min
Play Ratio: {stats['ratio']:.1f}%

*** TRUST SCORE: {trust_score} / 100 ({trust_level}) ***
Persona: {persona_name}
Persona Mode: {persona_tone}

Recent Violations:
{chr(10).join(['- ' + v for v in stats['violations']])}

{judgment_guide}
=========================
"""
    else:
        behavior_report = f"""
=== Behavioral Report ===
(Stats Unavailable - Timeout)
*** TRUST SCORE: {trust_score} / 100 ({trust_level}) ***
Persona: {persona_name}
{judgment_guide}
=========================
"""

    # Manual substitution to bypass LangChain validation issues
    # Escape braces in content and instructions
    safe_text = request.text.replace("{", "{{").replace("}", "}}")
    safe_context = str(memory_context).replace("{", "{{").replace("}", "}}")
    if 'behavior_report' in locals():
         safe_report = behavior_report.replace("{", "{{").replace("}", "}}")
    else:
         safe_report = "(No Report)"

    
    final_prompt = f"""
You are "Alpine" (알파인), a high-performance AI study assistant.
Your user is **"{request.user_id}"** whom you address as **"주인님"** (Master).

{persona_instruction}

*** PERSONA SYSTEM (TRUST-BASED) ***
Your personality changes based on the user's TRUST SCORE:

4.  **Competence**: 
   - Even while insulting or obsessing, you execute commands efficiently.
   - If Low Trust & Game request -> REFUSE and INSULT MORE.

5.  **Game Detection Follow-up (CRITICAL)**:
   - **Excuse Detection**: If the user makes excuses for playing games, look for these patterns:
     * "한 판만 할게", "한 판만", "하나만 더", "조금만", "조금만 더", "이번만", "이번만 할게", "진짜 마지막", "마지막 한 판"
     * When you detect these excuses, check the [Behavioral Report] and [Semantic Memory] for recent violations.
     * If there's ANY recent violation or record of them saying the same thing, REFUSE firmly with:
       - "저번에도 그러셨잖아요! 안 됩니다!"
       - "또 그런 말 하시는 거예요? 안 됩니다!"
       - Set **action_code: NONE**, **judgment: PLAY**, **emotion: ANGRY**
   
   - **Agreement/Surrender Detection**: If the user agrees to stop playing, look for these patterns:
     * "알았어", "알았어요", "알겠어", "알겠어요", "그만할게", "그만할게요", "이제 끌게", "끌게", "종료할게"
     * When you detect agreement, IMMEDIATELY execute **KILL_APP** action:
       - Set **action_code: KILL_APP**
       - Set **action_detail** to the game process name (check [Semantic Memory] for recently detected games, or use "LeagueClient" if League of Legends was mentioned)
       - Set **judgment: PLAY**, **intent: COMMAND**
       - Message: "프로세스 종료합니다." or "롤 프로세스 종료합니다."
       - **emotion: SILLY** or **ANGRY**

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

*** LENGTH RULE: MAX 1-2 SENTENCES (CRITICAL) ***
- Absolutely NO Intro/Outro.
- Speak like a real person, not an AI.
- Keep it short.

*** CRITICAL GAME DETECTION LOGIC ***
Before processing, check if the input contains:
- **Excuse patterns**: "한 판만", "하나만 더", "조금만", "이번만", "마지막"
- **Agreement patterns**: "알았어", "알겠어", "그만할게", "끌게", "종료할게"

If excuse detected AND [Behavioral Report] shows violations → REFUSE (action_code: NONE)
If agreement detected → KILL_APP (action_detail: check [Semantic Memory] for "LeagueClient", "Riot Client", "League of Legends", or use "LeagueClient" as default)

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

            # [DEBUG] Game-related judgment log
            try:
                if data.get("judgment") == "PLAY":
                    print(
                        f"🎮 [Chat/Game][DEBUG] judgment=PLAY, "
                        f"intent={data.get('intent')}, "
                        f"action_code={data.get('action_code')}, "
                        f"action_detail={data.get('action_detail')}"
                    )
            except Exception as dbg_err:
                print(f"[Chat/Game][DEBUG] Log error: {dbg_err}")

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

            # [LOGIC HOOK] Handle Game Agreement Detection
            # If user agreed to stop playing and action_code is KILL_APP, use AI to detect game process from running apps
            if data.get("action_code") == "KILL_APP":
                action_detail = data.get("action_detail", "")
                
                # If action_detail is not set, detect game from running apps using AI
                if not action_detail or action_detail == "":
                    # Parse running apps from input text (format: [현재 실행 중인 앱: app1, app2, ...])
                    running_apps = []
                    apps_match = re.search(r'\[현재 실행 중인 앱:\s*([^\]]+)\]', request.text)
                    if apps_match:
                        apps_str = apps_match.group(1)
                        # Split by comma and clean up
                        running_apps = [app.strip() for app in apps_str.split(',') if app.strip()]
                    
                    # If we have running apps, use AI game detector to find the game process
                    if running_apps:
                        try:
                            print(f"🎮 [Game Detection] Detecting game from running apps: {running_apps[:5]}...")
                            game_detect_request = GameDetectRequest(apps=running_apps)
                            game_result = await game_detector.detect_games(game_detect_request)
                            
                            if game_result.is_game_detected and game_result.target_app:
                                detected_game = game_result.target_app
                                # Use detected_games list if available (more accurate)
                                if game_result.detected_games and len(game_result.detected_games) > 0:
                                    # Use the first detected game process name
                                    detected_game = game_result.detected_games[0]
                                data["action_detail"] = detected_game
                                print(f"🎮 [Game Detection] AI detected game process: {detected_game}")
                            else:
                                print(f"⚠️ [Game Detection] No game detected in running apps")
                                # Fallback: check memory context for recent violations
                                if memory_context:
                                    if "League" in memory_context or "Riot" in memory_context or "롤" in memory_context:
                                        data["action_detail"] = "LeagueClient"
                                    elif "Minecraft" in memory_context or "마인크래프트" in memory_context:
                                        data["action_detail"] = "Minecraft"
                        except Exception as e:
                            print(f"❌ [Game Detection] Error detecting game: {e}")
                            # Fallback to memory context
                            if memory_context:
                                if "League" in memory_context or "Riot" in memory_context or "롤" in memory_context:
                                    data["action_detail"] = "LeagueClient"
                    else:
                        # No running apps info, check memory context
                        if memory_context:
                            if "League" in memory_context or "Riot" in memory_context or "롤" in memory_context:
                                data["action_detail"] = "LeagueClient"
                            elif "Minecraft" in memory_context or "마인크래프트" in memory_context:
                                data["action_detail"] = "Minecraft"

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
