import asyncio
import grpc
import sys
import os

# Adjust path to find app module
sys.path.append("c:\\Users\\yoons\\OneDrive\\문서\\GitHub\\project-JIAA-DevOps\\jiaa-server-ai")

from app.protos import text_ai_pb2, text_ai_pb2_grpc

async def test_subgoals():
    # Using Production Endpoint (SSL)
    credentials = grpc.ssl_channel_credentials()
    async with grpc.aio.secure_channel('api.jiobserver.cloud:443', credentials) as channel:
        stub = text_ai_pb2_grpc.TextAIServiceStub(channel)
        
        print("\n--- Sending Subgoal Request ---")
        goal = "Make a Todo App"
        request = text_ai_pb2.GoalRequest(goal_text=goal)
        
        try:
            print(f"Goal: {goal}")
            response = await stub.GenerateSubgoals(request)
            print("Response Subgoals:")
            for sub in response.subgoals:
                print(f"- {sub}")
        except Exception as e:
            print(f"RPC Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_subgoals())
