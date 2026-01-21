import grpc
import sys
import os

# Add generated protos to path
sys.path.append("./jiaa-client/dev_3/resources/tracking_service")
# (Assuming the proto files are available locally or I need to generate/mock them)
# Wait, let's use the 'unified_service.py' logic or similar. 
# Actually, I can use the EXISTING 'grpc_client.ts' or a simple python script if I have the protobufs.
# 'unified_service.py' has the 'TextAIServiceStub'. Let's reuse that structure.

# But simpler: I will assume the user has the proto files generated in 'jiaa-server-ai/app/protos'.
# I will make this script run from 'jiaa-server-ai' root maybe?
# Or just copy the necessary imports.

# Let's try to run a simple script that mimics 'tests/test_scenario_flow.py' but points to REAL SERVER.
# tests/test_scenario_flow.py uses 'grpc.aio.insecure_channel'. I should use that.

import asyncio
import grpc
# Adjust path to find app module
sys.path.append("c:\\Users\\yoons\\OneDrive\\문서\\GitHub\\project-JIAA-DevOps\\jiaa-server-ai")

from app.protos import text_ai_pb2, text_ai_pb2_grpc

async def test_persona():
    # Connect to the External Ingress (or localhost port-forwarded)
    # Using Ingress URL: 'ai.jiobserver.cloud:80' (if configured) or direct NodePort?
    # User provided 'ai.jiobserver.cloud' in ingress, but I don't have DNS setup locally maybe.
    # I'll use 'localhost:50051' via PORT FORWARDING for reliability.
    
    async with grpc.aio.insecure_channel('localhost:50059') as channel:
        stub = text_ai_pb2_grpc.TextAIServiceStub(channel)
        
        print("\n--- Sending Chat Request (User: dev1) ---")
        request = text_ai_pb2.ChatRequest(
            text="나 공부 열심히 했어! 칭찬해줘.",
            client_id="dev2"
        )
        
        try:
            response = await stub.Chat(request)
            print(f"Response: {response.message}")
            print(f"Emotion: {response.emotion}")
        except Exception as e:
            print(f"RPC Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_persona())
