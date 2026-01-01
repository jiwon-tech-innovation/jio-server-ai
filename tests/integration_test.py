import asyncio
import grpc
import requests
import json
import os
import sys
import os

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
    filename = "test_command.mp3"
    
    # Generate MP3
    tts = gTTS(text=text_to_say, lang='ko')
    tts.save(filename)
    
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = audio_pb2_grpc.SpeechServiceStub(channel)
        
        async def request_generator():
            chunk_size = 1024 * 16
            with open(filename, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data: break
                    yield audio_pb2.AudioRequest(audio_data=data, is_final=False)
            yield audio_pb2.AudioRequest(audio_data=b'', is_final=True)

        try:
            response = await stub.SendAudioStream(request_generator())
            print(f"AI Text: {response.text}")
            print(f"Command: {response.command}")
            print(f"Parameter: {response.parameter}")
            
            if response.command == "OPEN" and "Spotify" in response.parameter:
                print(f"{GREEN}>> PASS: Command successfully extracted.{RESET}")
            else:
                print(f"{RED}>> FAIL: Command mismatch.{RESET}")
        except Exception as e:
            print(f"{RED}>> FAIL: gRPC Error: {e}{RESET}")
            
    if os.path.exists(filename):
        os.remove(filename)

def test_dev4_http_classify_study():
    print(f"\n{GREEN}[TEST 2] Dev 4: HTTP URL Classification (STUDY){RESET}")
    # Spring Boot Tutorial URL (Title likely contains "Spring Boot")
    url = "http://localhost:8000/api/v1/intelligence/classify"
    payload = {
        "content_type": "URL",
        "content": "https://www.youtube.com/watch?v=9j12kDw99u4" # Spring Boot Tutorial
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
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
    # Funny Cat Video
    url = "http://localhost:8000/api/v1/intelligence/classify"
    payload = {
        "content_type": "URL",
        "content": "https://www.youtube.com/watch?v=XyNlqQId-nk" # Funny Video
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

async def main():
    print("=== JIAA Integration Tests ===")
    await test_dev1_grpc_command()
    test_dev4_http_classify_study()
    test_dev4_http_classify_play()

if __name__ == "__main__":
    asyncio.run(main())
