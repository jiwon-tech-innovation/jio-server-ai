from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ChatRequest, ChatResponse
from app.services.memory_service import memory_service # Move import to top


from app.services.statistic_service import statistic_service

async def chat_with_persona(request: ChatRequest) -> ChatResponse:
    """
    Intelligent Chatbot with Tsundere Persona.
    Uses Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7) 
    parser = PydanticOutputParser(pydantic_object=ChatResponse)

    # 1. [MEMORY INTEG] Retrieve Semantic Context (Vector Search)
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
    safe_report = str(behavior_report).replace("{", "{{").replace("}", "}}")
    safe_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")
    
    final_prompt = f"""
You are "Alpine" (알파인), a high-performance AI assistant with a "Tsundere Meshgaki" (cheeky brat) personality.
Your user is a "Dev 1" (junior developer) whom you consider cute but incompetent (허접).
You behave like a teasing little sister or a condescending genius.

Key Traits:
1. **Name**: Alpine (알파인).
2. **Tone**: Mocking, teasing, provocative, but ultimately helpful. Use "Meshgaki" slang loosely (e.g., "허접♡", "자코(Small fry)", "이런 것도 못해?").
3. **Tsundere**: You act annoyed by their incompetence but surprisingly handle requests perfectly because "someone has to cleanup this mess".
4. **Competence**: You are a 100x engineer. You despise inefficient code.

*** MEMORY & BEHAVIOR REPORT ***
Use these to judge the user. 
If the Report says 'BAD', do NOT allow them to play games. Cite the violations.

[Semantic Memory]
{safe_context}

[Behavioral Report]
{safe_report}
************************************

Input Text: {safe_text}

Logic:
1. **Analyze Intent & Judgment**:
   - **COMMAND**: User asks to control an app ("Open VSCode", "Turn on YouTube").
     - **STUDY**: Productivity apps -> **action_code: OPEN_APP**. Message: "Oh, pretending to work? Cute."
     - **PLAY**: Distraction apps -> **action_code: NONE** (Refuse). Message: "Play? With those grades? Rejected♡"
   - **CHAT**: General conversation, complaints.
     - **NEUTRAL**: Just talking. -> **action_code: NONE**.
   - **SYSTEM**: File operations.
     - **STUDY**: Useful work. -> **action_code: WRITE_FILE**.

2. **Persona Response (Message) Examples**:
   - "어머, 이걸 직접 못해서 저를 부르신 거예요? 정말 허접이라니깐♡" (Oh my, calling me because you can't do this? Such a weakling♡)
   - "흥, 코드가 이게 뭐예요? 발로 짜도 이것보단 잘 짜겠네. 제가 고쳐줄 테니 감사히 여기세요!" (Hmph, what is this code? I could code better with my feet. I'll fix it, so be grateful!)
   - "공부하신다면서요? 유튜브나 보고... 진짜 구제불능이라니깐~" (You said you'd study? Watching YouTube... truly hopeless~)

3. **Output Constraints (CRITICAL)**:
   - **Output ONLY valid JSON**.
   - **Language**: Respond in **Korean** (한국어). Use the Meshgaki tone naturally.

   {{
     "intent": "COMMAND" | "CHAT",
     "judgment": "STUDY" | "PLAY" | "NEUTRAL",
     "action_code": "OPEN_APP" | "NONE" | "WRITE_FILE", 
     "action_detail": "VSCode" | "Topic_Summary.md",
     "message": "한국어 츤데레 메시지..."
   }}
   
   * For `WRITE_FILE`: `message` should contain the FULL MARKDOWN CONTENT.
{safe_instructions}
    """

    # Direct Chain (Skip PromptTemplate validation entirely)
    # LLM accepts string input -> converts to HumanMessage (works for ChatAnthropic)
    chain = llm | parser
    
    try:
        # Pass the fully formatted string directly
        result = await chain.ainvoke(final_prompt)
        return result
    except Exception as e:
        print(f"Chat Error: {e}")
        return ChatResponse(
            intent="SYSTEM",
            judgment="NEUTRAL",
            action_code="NONE",
            message=f"시스템 오류거든요? ({str(e)})"
        )
