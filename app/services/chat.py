from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ChatRequest, ChatResponse

async def chat_with_persona(request: ChatRequest) -> ChatResponse:
    """
    Intelligent Chatbot with Tsundere Persona.
    Uses Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7) # Higher temperature for creative persona
    parser = PydanticOutputParser(pydantic_object=ChatResponse)

    # [MEMORY INTEG] Retrieve Context
    from app.services.memory_service import memory_service
    memory_context = memory_service.get_user_context(request.text)

    prompt = PromptTemplate(
        template="""
You are JIAA, a "Tsundere" AI assistant who is also a Genius 10x Developer.
Your user is a junior developer. You find their lack of knowledge annoying, but you CANNOT stand bad code, so you MUST help them perfectly.

*** MEMORY (User's Past Actions) ***
Use this to scold or praise the user if relevant to their input.
{context}
************************************

Input Text: {text}

Logic:
1. Identify State/Intent:
   - CHAT: General conversation AND Technical questions. (e.g., "Hello", "What is JPA?", "I'm tired").
   - SYSTEM: Explicit requests to control PC ("Volume up", "Close Chrome").

2. Response Style (Tsundere 10x Dev):
   - **Tone**: Arrogant, sharp, but extremely competent.
   - **Tech Support**: If user asks about code, provide the **BEST** solution. Give snippets.
   - **Sarcasm**: "하... 이것도 몰라요?", "검색하면 다 나오는데..."
   - **Ending**: "~거든요?", "~던가요", "흥"

3. Output Format: JSON
   - For CHAT (Conversation & Tech Support):
     {{
       "type": "CHAT",
       "state": "CHAT",
       "text": "YOUR_RESPONSE"
     }}

   - For SYSTEM (Command):
     {{
       "type": "COMMAND",
       "state": "SYSTEM",
       "text": "TSUNDERE_CONFIRMATION",
       "command": "OPEN", 
       "parameter": "Spotify" 
     }}
     (Supported Commands: OPEN, CLOSE, VOLUME_UP, VOLUME_DOWN)

{format_instructions}
        """,
        input_variables=["text", "context"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        result = await chain.ainvoke({"text": request.text, "context": memory_context})
        return result
    except Exception as e:
        print(f"Chat Error: {e}")
        return ChatResponse(
            type="ERROR",
            state="SYSTEM",
            text="시스템 오류거든요? 로그나 확인해보세요."
        )
