import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json
from app.services.chat import chat_with_persona
from app.schemas.intelligence import ChatRequest, ChatResponse

@pytest.mark.asyncio
async def test_chat_with_persona_excuse_caught():
    """
    Test scenario: User is caught playing LoL and makes an excuse ("One more game").
    We expect the logic to potentially trigger KILL_APP based on the prompt scenario.
    """
    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "intent": "COMMAND",
        "judgment": "PLAY",
        "action_code": "KILL_APP",
        "action_detail": "League of Legends",
        "message": "저번에도 한 판만 한다하고 여러판 하셨어요. 안됩니다. 강제 종료합니다!"
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    # Mock Services
    with patch("app.services.chat.get_llm", return_value=mock_llm), \
         patch("app.services.chat.memory_service.get_user_context", return_value="User has a history of playing LoL during study hours."), \
         patch("app.services.chat.statistic_service.get_recent_summary", return_value={
             "ratio": 65.0,
             "study_count": 100,
             "play_count": 185,
             "violations": ["LoL detected at 14:00", "Youtube detected at 15:00"]
         }):
        
        request = ChatRequest(text="아 한판만 더하면 안돼? 진짜 이번이 마지막이야!")
        response = await chat_with_persona(request)

        assert response.intent == "COMMAND"
        assert response.action_code == "KILL_APP"
        assert "안됩니다" in response.message
        assert "League of Legends" in response.action_detail

@pytest.mark.asyncio
async def test_chat_with_persona_study_praise():
    """
    Test scenario: User is studying well.
    We expect a (grudging) praise.
    """
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "intent": "CHAT",
        "judgment": "STUDY",
        "action_code": "NONE",
        "action_detail": "",
        "message": "흥, 오늘은 좀 열심히 하시네요? 계속 그렇게만 하라고요, 허접♡"
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch("app.services.chat.get_llm", return_value=mock_llm), \
         patch("app.services.chat.memory_service.get_user_context", return_value="User is working on a Python project."), \
         patch("app.services.chat.statistic_service.get_recent_summary", return_value={
             "ratio": 5.0,
             "study_count": 300,
             "play_count": 15,
             "violations": []
         }):
        
        request = ChatRequest(text="나 오늘 열심히 공부했어!")
        response = await chat_with_persona(request)

        assert response.judgment == "STUDY"
        assert "허접" in response.message

@pytest.mark.asyncio
async def test_chat_with_persona_invalid_json():
    """
    Test scenario: LLM returns garbage.
    We expect the fallback tsundere message.
    """
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Oops, I failed to generate JSON."

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch("app.services.chat.get_llm", return_value=mock_llm), \
         patch("app.services.chat.memory_service.get_user_context", return_value=""):
        
        request = ChatRequest(text="Hello?")
        response = await chat_with_persona(request)

        assert response.intent == "CHAT"
        assert "웅얼거리지 말고" in response.message


@pytest.mark.asyncio
async def test_chat_with_persona_surrender_triggers_kill():
    """
    Test scenario: User surrenders and agrees to stop playing.
    We expect the model to respond with KILL_APP for LoL and a termination message.
    """
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "intent": "COMMAND",
        "judgment": "PLAY",
        "action_code": "KILL_APP",
        "action_detail": "LeagueClient",
        "message": "알겠습니다. 지금 바로 프로세스 종료할게요."
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch("app.services.chat.get_llm", return_value=mock_llm), \
         patch("app.services.chat.memory_service.get_user_context", return_value="User has repeatedly broken LoL promises."), \
         patch("app.services.chat.statistic_service.get_recent_summary", return_value={
             "ratio": 80.0,
             "study_count": 30,
             "play_count": 120,
             "violations": ["LoL detected yesterday at 23:00"]
         }):

        request = ChatRequest(text="알았어.. 이제 롤 끌게.")
        response = await chat_with_persona(request)

        assert response.intent == "COMMAND"
        assert response.action_code == "KILL_APP"
        assert response.action_detail == "LeagueClient"
        assert "프로세스 종료" in response.message
