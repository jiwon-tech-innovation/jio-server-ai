import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

from app.services.chat import chat_with_persona
from app.schemas.intelligence import ChatRequest


@pytest.mark.asyncio
async def test_game_flow_excuse_then_surrender():
    """
    High-level conversational flow test:
    1) User makes an excuse to keep playing LoL.
    2) User later agrees to stop.
    We simulate LLM responses and verify that the second turn triggers KILL_APP.
    """
    # First turn: excuse ("한 판만")
    mock_llm_response_excuse = MagicMock()
    mock_llm_response_excuse.content = json.dumps({
        "intent": "COMMAND",
        "judgment": "PLAY",
        "action_code": "NONE",
        "action_detail": "",
        "message": "또 한 판만이세요? 안 됩니다, 주인님."
    })

    # Second turn: surrender ("알았어..")
    mock_llm_response_surrender = MagicMock()
    mock_llm_response_surrender.content = json.dumps({
        "intent": "COMMAND",
        "judgment": "PLAY",
        "action_code": "KILL_APP",
        "action_detail": "LeagueClient",
        "message": "좋아요, 지금 바로 롤 프로세스 종료할게요."
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = [
        mock_llm_response_excuse,
        mock_llm_response_surrender,
    ]

    with patch("app.services.chat.get_llm", return_value=mock_llm), \
         patch("app.services.chat.memory_service.get_user_context", return_value="LoL was detected recently while the user was supposed to study."), \
         patch("app.services.chat.statistic_service.get_recent_summary", return_value={
             "ratio": 70.0,
             "study_count": 60,
             "play_count": 140,
             "violations": ["LoL detected at 22:00 with 'just one more' excuse"]
         }):

        # Step 1: excuse
        req_excuse = ChatRequest(text="아 진짜 한 판만 더 하면 안 돼? 이번이 마지막이야.")
        res_excuse = await chat_with_persona(req_excuse)

        assert res_excuse.intent == "COMMAND"
        assert res_excuse.judgment == "PLAY"
        assert res_excuse.action_code in ("NONE", "MINIMIZE_APP")

        # Step 2: surrender
        req_surrender = ChatRequest(text="알았어.. 이제 진짜 롤 끌게.")
        res_surrender = await chat_with_persona(req_surrender)

        assert res_surrender.intent == "COMMAND"
        assert res_surrender.action_code == "KILL_APP"
        assert res_surrender.action_detail == "LeagueClient"
        assert "롤 프로세스 종료" in res_surrender.message or "프로세스 종료" in res_surrender.message


