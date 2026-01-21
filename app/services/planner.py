
from typing import List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.core.llm import get_llm, SONNET_MODEL_ID, HAIKU_MODEL_ID
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- Subgoal Schemas ---
class GoalList(BaseModel):
    subgoals: List[str] = Field(description="List of actionable sub-tasks")

# --- Quiz Schemas ---
class QuizItem(BaseModel):
    question: str = Field(description="The quiz question")
    options: List[str] = Field(description="List of 4 options")
    answer: str = Field(description="The correct answer text (must be exact match with one of options)")
    explanation: str = Field(description="Explanation of the answer")

class SubgoalQuiz(BaseModel):
    subgoal: str = Field(description="The sub-topic or goal this quiz covers (e.g. 'Concept', 'Application')")
    quizzes: List[QuizItem] = Field(description="List of quizzes for this sub-topic")

class QuizResponse(BaseModel):
    items: List[SubgoalQuiz] = Field(description="List of quiz groups by sub-topic")

# -------------------------------------------------------------------------
# Planner Logic (Powered by Claude 3.5 Sonnet)
# -------------------------------------------------------------------------

async def generate_subgoals(goal: str) -> List[str]:
    """
    Breaks down a high-level goal into actionable sub-goals using Claude 3.5 Sonnet.
    Sonnet provides better reasoning for logical breakdowns.
    """
    # [Config] Use Sonnet for Deep Planning
    llm = get_llm(model_id=SONNET_MODEL_ID, temperature=0.7)
    parser = PydanticOutputParser(pydantic_object=GoalList)

    prompt = PromptTemplate(
        template="""
    You are an expert technical project manager.
    Your task is to break down the user's high-level goal into 4-8 CONCRETE, ACTIONABLE sub-tasks.
    
    User Goal: "{goal}"
    
    Rules:
    1. **Structure**: Sequence logical steps (Setup -> Core Logic -> UI -> Deploy).
    2. **Clarity**: Each task must be clear and under 15 words.
    3. **Language**: Korean (한국어).
    4. **Output**: JSON only.
    
    {format_instructions}
        """,
        input_variables=["goal"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        print(f"🧠 [Planner] Sonnet Planning for: {goal}")
        result = await chain.ainvoke({"goal": goal})
        return result.subgoals
    except Exception as e:
        print(f"Planner Error: {e}")
        return [f"계획 생성 실패: {str(e)}"]

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
async def _generate_quiz_safe(topic: str, difficulty: str) -> List[dict]:
    """
    Internal safe generation with retries.
    """
    # [Optimized] Use Haiku for Speed (Server Response < 10s)
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7)
    parser = PydanticOutputParser(pydantic_object=QuizResponse)
    
    prompt = PromptTemplate(
        template="""
    You are an Expert CS Tutor.
    Create a comprehensive quiz for the topic "{topic}" ({difficulty} level).
    
    Target Audience: Junior Developer.
    Language: Korean.
    
    Requirements:
    1. **Structure**: Group questions by sub-topics (e.g. 'Key Concepts', 'Advanced Usage', 'Best Practices').
    2. **Content**: Create at least 3 sub-topics, with 1-2 questions each.
    3. **Verification**: Questions should verify core understanding.
    4. **Format**: 4 Options per question. Providing the full text answer string.
    5. **Answer**: The 'answer' field MUST be an exact string match to one of the options.
    6. **Language**: Question and Options in Korean.
    
    {format_instructions}
        """,
        input_variables=["topic", "difficulty"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    chain = prompt | llm | parser
    
    print(f"🧠 [Quiz] Haiku Generating Quiz for: {topic} ({difficulty})")
    result = await chain.ainvoke({"topic": topic, "difficulty": difficulty})
    
    # Convert Pydantic models to list of dicts (Nested Structure)
    return [item.dict() for item in result.items]


async def generate_quiz(topic: str, difficulty: str = "Medium") -> List[dict]:
    """
    Generates a technical quiz based on the topic using Claude 3.5 Sonnet.
    Returns raw dict list for easy usage.
    Wrapper handles final exceptions after retries.
    """
    try:
        return await _generate_quiz_safe(topic, difficulty)
    except Exception as e:
        print(f"❌ [Quiz] Fatal Generation Error after retries: {e}")
        return []

