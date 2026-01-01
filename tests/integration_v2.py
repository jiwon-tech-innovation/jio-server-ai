import asyncio
import grpc
import requests
import json
import os
import sys

# Ensure app module can be imported
sys.path.append(os.getcwd())

from gtts import gTTS
from app.protos import audio_pb2, audio_pb2_grpc

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

async def test_dev1_grpc_command():
    print(f"\n{GREEN}[TEST 1] Dev 1: gRPC Audio Command (Spotify){RESET}")
    text_to_say = "노래 듣고 싶어 Spotify 켜줘"
    filename = "test_command_v2.mp3"
    
    # Generate MP3
    tts = gTTS(text=text_to_say, lang='ko')
    tts.save(filename)
    
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        # Changed Stub Name
        stub = audio_pb2_grpc.AudioServiceStub(channel)
        
        async def request_generator():
            chunk_size = 1024 * 16
            with open(filename, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data: break
                    # Changed Request Fields
                    yield audio_pb2.AudioRequest(audio_data=data, is_final=False, timestamp=123456789)
            yield audio_pb2.AudioRequest(audio_data=b'', is_final=True, timestamp=123456789)

        try:
            # Changed Method Name
            response = await stub.TranscribeAudio(request_generator())
            print(f"Transcript (STT): {response.transcript}")
            
            # Parse Intent (JSON)
            try:
                intent_data = json.loads(response.intent)
                print(f"Intent JSON: {intent_data}")
                
                ai_text = intent_data.get("text", "")
                state = intent_data.get("state", "UNKNOWN")
                print(f"AI Text (TTS): {ai_text}")
                print(f"State (Classifier): {state}")
                
                command = intent_data.get("command")
                param = intent_data.get("parameter")

                # Check Logic
                if intent_data.get("type") == "COMMAND" and "Spotify" in str(param):
                    print(f"{GREEN}>> PASS: Command 'Spotify' recognized.{RESET}")
                else:
                    print(f"{RED}>> FAIL: Command mismatch.{RESET}")
                    
                if state in ["STUDY", "PLAY"]:
                     print(f"{GREEN}>> PASS: State '{state}' is valid.{RESET}")
                else:
                     print(f"{RED}>> FAIL: State missing or invalid.{RESET}")
                    
            except json.JSONDecodeError:
                print(f"{RED}>> FAIL: Intent is not valid JSON: {response.intent}{RESET}")

        except Exception as e:
            print(f"{RED}>> FAIL: gRPC Error: {str(e)}{RESET}")
            
    if os.path.exists(filename):
        os.remove(filename)

def test_dev4_http_classify_study():
    print(f"\n{GREEN}[TEST 2] Dev 4: HTTP URL Classification (STUDY){RESET}")
    # Use a reliable dev site instead of YouTube (which blocks bots)
    url = "http://localhost:8000/api/v1/classify"
    payload = {
        "content_type": "URL",
        "content": "https://github.com/spring-projects/spring-boot" # Reliable Dev Content
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 404:
             print(f"{RED}>> FAIL: 404 Not Found.{RESET}")
             return

        data = response.json()
        print(f"Response: {data}")
        
        if data.get("result") == "STUDY":
            print(f"{GREEN}>> PASS: Correctly classified as STUDY.{RESET}")
        else:
            print(f"{RED}>> FAIL: Expected STUDY, got {data.get('result')}{RESET}")
    except Exception as e:
        print(f"{RED}>> FAIL: HTTP Error: {e}{RESET}")

def test_dev4_http_classify_play():
    print(f"\n{GREEN}[TEST 3] Dev 4: HTTP URL Classification (PLAY){RESET}")
    url = "http://localhost:8000/api/v1/classify"
    payload = {
        "content_type": "URL",
        "content": "https://www.youtube.com/watch?v=XyNlqQId-nk" # Funny Cat Video
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        print(f"Response: {data}")
        
        if data.get("result") == "PLAY":
            print(f"{GREEN}>> PASS: Correctly classified as PLAY.{RESET}")
        else:
            print(f"{RED}>> FAIL: Expected PLAY, got {data.get('result')}{RESET}")
    except Exception as e:
        print(f"{RED}>> FAIL: HTTP Error: {e}{RESET}")

async def test_dev1_grpc_create_file():
    print(f"\n{GREEN}[TEST 4] Dev 1: gRPC Create File Command (Memo){RESET}")
    text_to_say = "지금 말한 내용 바탕화면에 저장해줘"
    filename = "test_file_cmd.mp3"
    
    tts = gTTS(text=text_to_say, lang='ko')
    tts.save(filename)
    
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = audio_pb2_grpc.AudioServiceStub(channel)
        async def request_generator():
            chunk_size = 1024 * 16
            with open(filename, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data: break
                    yield audio_pb2.AudioRequest(audio_data=data, is_final=False, timestamp=123)
            yield audio_pb2.AudioRequest(audio_data=b'', is_final=True, timestamp=123)

        try:
            response = await stub.TranscribeAudio(request_generator())
            intent_data = json.loads(response.intent)
            print(f"Intent JSON: {intent_data}")
            
            if intent_data.get("command") == "CREATE_FILE":
                 print(f"{GREEN}>> PASS: Command 'CREATE_FILE' recognized.{RESET}")
            else:
                 print(f"{RED}>> FAIL: Expected CREATE_FILE, got {intent_data.get('command')}{RESET}")
                 
        except Exception as e:
            print(f"{RED}>> FAIL: gRPC Error: {e}{RESET}")
    if os.path.exists(filename): os.remove(filename)

async def main():
    print("=== JIAA Integration Tests V2 (New Proto) ===")
    await test_dev1_grpc_command()
    test_dev4_http_classify_study()
    test_dev4_http_classify_play()
    await test_dev1_grpc_create_file()

if __name__ == "__main__":
    asyncio.run(main())
