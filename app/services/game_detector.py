from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.game import GameDetectRequest, GameDetectResponse

async def detect_games(request: GameDetectRequest) -> GameDetectResponse:
    """
    Detects if any games are running from the app list using Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.0)
    parser = PydanticOutputParser(pydantic_object=GameDetectResponse)

    apps_str = ", ".join(request.apps)

    prompt = PromptTemplate(
        template="""
You are JIAA's strict anti-gaming supervisor.
Your job is to scan the list of running processes and detect any VIDEO GAMES.

Input Apps:
{apps}

*** CRITICAL RULES ***
1. **Target**: Identify explicit video games (e.g., "League of Legends", "Minecraft", "Overwatch", "MapleStory", "Valorant", "Steam", "Battle.net").
2. **Ignore**:
   - Web Browsers (Chrome, Safari, Firefox)
   - Development Tools (VS Code, Python, Terminal, iTerm2, Xcode)
   - Communication Apps (Discord, Slack, KakaoTalk) -> These are NOT games for this check.
   - System Processes (Finder, WindowServer, etc.)
3. **Steam/Launchers**: If "steam_osx" or "Battle.net" is running, count it as a game (the user is likely browsing games or playing).

Output strictly valid JSON only. No markdown, no "```json" blocks, no conversation.
Example format:
{{
    "is_game_detected": true,
    "target_app": "League of Legends",
    "detected_games": ["League of Legends"],
    "message": "Do not play games during work hours!",
    "confidence": 1.0
}}
        """,
        input_variables=["apps"],
    )
    chain = prompt | llm | parser

    try:
        result = await chain.ainvoke({
            "apps": apps_str
        })
        print(f"[GameDetector] Result: {result}")
        return result

    except Exception as e:
        print(f"Game Detector Error: {e}")
        return GameDetectResponse(
            is_game_detected=False, 
            message=f"Detection failed: {str(e)}", 
            confidence=0.0
        )
