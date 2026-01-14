import asyncio
from app.services import planner

async def test_planner():
    goal = "리액트 기반의 투두 앱을 만들고 파이어베이스와 연동해줘"
    print(f"🎯 Testing Goal: {goal}")
    
    subgoals = await planner.generate_subgoals(goal)
    
    print("\n✅ Generated Subgoals:")
    for i, sg in enumerate(subgoals, 1):
        print(f"{i}. {sg}")

if __name__ == "__main__":
    asyncio.run(test_planner())
