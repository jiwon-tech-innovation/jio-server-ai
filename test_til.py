import asyncio
import grpc
import sys
import os

# App directory needs to be in path if not already
sys.path.append('/app')

from app.protos import text_ai_pb2, text_ai_pb2_grpc

async def test():
    print("Testing gRPC Connection to localhost:50051...")
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = text_ai_pb2_grpc.TextAIServiceStub(channel)
        print("Sending 'TIL Daily Report (Auto-Generated)' request...")
        try:
            response = await stub.Chat(text_ai_pb2.ChatRequest(
                text="TIL Daily Report (Auto-Generated)", 
                client_id="test-script"
            ))
            print(f"✅ Response Received!")
            print(f"Action Code: {response.action_code}")
            print(f"Action Detail: {response.action_detail}")
            print(f"Message Length: {len(response.message)}")
            if response.message:
                print(f"Message Preview: {response.message[:200]}...")
            else:
                print("❌ Message is empty!")
                
            if response.action_code == "WRITE_FILE" and len(response.message) > 50:
                 print("\n🎉 SUCCESS: Server contract satisfied!")
            else:
                 print("\n⚠️ WARNING: Contract might be violated (Check action code or content length)")
                 
        except Exception as e:
            print(f"❌ gRPC Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
