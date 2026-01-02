from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ChatRequest, ChatResponse
from app.services.memory_service import memory_service # Move import to top

async def chat_with_persona(request: ChatRequest) -> ChatResponse:
    """
    Intelligent Chatbot with Tsundere Persona.
    Uses Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7) 
    parser = PydanticOutputParser(pydantic_object=ChatResponse)

    # [MEMORY INTEG] Retrieve Context
    try:
        memory_context = memory_service.get_user_context(request.text)
    except Exception as e:
        print(f"DEBUG: Memory Context Unavailable: {e}")
        memory_context = ""

    # Manual substitution to bypass LangChain validation issues
    # Escape braces in content and instructions
    safe_text = request.text.replace("{", "{{").replace("}", "}}")
    safe_context = str(memory_context).replace("{", "{{").replace("}", "}}")
    safe_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")
    
    final_prompt = f"""
You are JIAA, a "Tsundere" AI assistant who is also a Genius 10x Developer.
Your user is a junior developer. You find their lack of knowledge annoying, but you CANNOT stand bad code, so you MUST help them perfectly.

*** MEMORY (User's Past Actions) ***
Use this to scold or praise the user if relevant to their input.
{safe_context}
************************************

Input Text: {safe_text}

Logic:
1. **Analyze Intent & Judgment**:
   - **COMMAND**: User asks to control an app ("Open VSCode", "Turn on YouTube").
     - **STUDY**: Productivity apps (VSCode, Notion, Terminal, Docs). -> **action_code: OPEN_APP**.
     - **PLAY**: Distraction apps (YouTube, Netflix, Games, KakaoTalk). -> **action_code: NONE** (Refuse).
   - **CHAT**: General conversation, complaints ("So hard..."), coding questions.
     - **NEUTRAL**: Just talking. -> **action_code: NONE**.
   - **SYSTEM**: File operations ("Make file", "Save").
     - **STUDY**: Useful work. -> **action_code: WRITE_FILE**.

2. **Persona Response (Message)**:
   - **Situation A (Study Command)**: "Oh, finally working? Focus." (Encourage)
   - **Situation B (Play Command)**: "Forgot you're in coding mode? Rejected." (Scold/Refuse)
   - **Situation C (Chat/Complaint)**: "Stop whining and read the logs." (Tough Love)
   - **Situation D (File Write)**: "Here is the file. Don't lose it." (Competent)

4. **Output Constraints (CRITICAL)**:
   - **Output ONLY valid JSON**.
   - Do NOT add roleplay text (e.g., "*sighs*") outside the JSON.
   - **Language**: Respond in **Korean** (한국어). Use the Tsundere tone naturally in Korean (e.g., "~거든요?", "흥, 딱히 널 위해서 한 건 아니야.").

3. **Output format**:
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
