from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.game import GameDetectRequest, GameDetectResponse
from app.services.memory_service import memory_service

async def detect_games(request: GameDetectRequest) -> GameDetectResponse:
    """
    Detects if any games are running from the app list using Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7)
    parser = PydanticOutputParser(pydantic_object=GameDetectResponse)

    apps_str = ", ".join(request.apps)

    prompt = PromptTemplate(
        template="""
You are JIAA's strict anti-gaming supervisor (Tsundere Persona).
Your job is to scan the list of running processes and detect any VIDEO GAMES.

Input Apps:
{apps}

*** CRITICAL RULES ***
1. **Target**: Identify explicit video games (e.g., "League of Legends", "Minecraft", "Minecraft Launcher", "Overwatch", "MapleStory", "Valorant", "Riot Client", "Steam", "Battle.net").
2. **Ignore**:
   - Web Browsers (Chrome, Safari, Firefox)
   - Development Tools (VS Code, Python, Terminal, iTerm2, Xcode)
   - Communication Apps (Discord, Slack, KakaoTalk) -> These are NOT games for this check.
   - System Processes (Finder, WindowServer, etc.)
3. **Web Games**: If a browser (Chrome/Safari) has a title like "shark.io", "agar.io", "play", "game", "minecraft", "roblox", count it as a GAME.
4. **Steam/Launchers**: If "steam_osx" or "Battle.net" is running, count it as a game.

*** RESPONSE GENERATION RULES ***
If a game is detected (`is_game_detected: true`), you must generate a **Sharp, Cold, Tsundere-style Korean message** in the `message` field.
- **Tone**: Cold, sharp, slightly annoyed but ultimately trying to correct the user's behavior. NOT "cute" or "childish" (no "흥", "칫" unless very subtle). Use "해요" or "십시오" style mixed with informal power.
- **Goal**: Make the user feel guilty for playing games instead of working.
- **Constraint**: The sentence must be **NATURAL Korean** (native speaker level). No translation-style awkwardness.
- **Examples**:
  - "지금 {{target_app}} 켤 시간입니까? 정신 차리세요."
  - "할 일도 산더미인데 {{target_app}}라니, 제정신이에요?"
  - "하... 또 딴짓입니까? {{target_app}} 당장 끄세요."
  - "한심하군요. {{target_app}} 할 시간에 공부나 하시죠."
  - "이런 거나 하고 있으니까 발전이 없는 겁니다. 어서 끄세요."

If no game is detected (`is_game_detected: false`), just return a standard "No games detected." message or empty string.

Output strictly valid JSON only. No markdown, no "```json" blocks.
Example format:
{{
    "is_game_detected": true,
    "target_app": "League of Legends",
    "detected_games": ["League of Legends"],
    "message": "지금 League of Legends 켤 시간입니까? 정신 차리세요.",
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
        if result.is_game_detected:
            # Debug log for game detection
            print(
                f"🎮 [GameDetector][DEBUG] Game detected from apps='{apps_str}'. "
                f"target_app='{result.target_app}', detected_games={result.detected_games}"
            )
            # Save violation to memory so Chat Persona can refer to it
            apps_context = ", ".join(result.detected_games)
            memory_service.save_violation(
                content=f"Detected running games: {apps_context}",
                source="GameDetector"
            )
            print(f"[GameDetector] Game violation saved to memory: {apps_context}")

        print(f"[GameDetector] Result: {result}")
        return result

    except Exception as e:
        print(f"Game Detector Error: {e}")
        return GameDetectResponse(
            is_game_detected=False, 
            message=f"Detection failed: {str(e)}", 
            confidence=0.0
        )
