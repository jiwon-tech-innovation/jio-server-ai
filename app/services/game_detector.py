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

Output JSON with:
- is_game_detected: true/false
- target_app: The name of the MAIN game process found (or null).
- detected_games: List of all game names found.
- message: A strict message scolding the user if a game is found.
- confidence: 0.0 to 1.0 (1.0 if sure).

{format_instructions}

IMPORTANT: Output ONLY the JSON object.
        """,
        input_variables=["apps"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser

    try:
        result = await chain.ainvoke({
            "apps": apps_str
        })
        return result

    except Exception as e:
        print(f"Game Detector Error: {e}")
        return GameDetectResponse(
            is_game_detected=False, 
            message=f"Detection failed: {str(e)}", 
            confidence=0.0
        )
