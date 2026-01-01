import asyncio
import grpc
import sys
import os
from gtts import gTTS

# Ensure app modules are found
sys.path.append(os.getcwd())

from app.protos import audio_pb2, audio_pb2_grpc

async def test_real_audio_stream():
    """
    Generates TTS audio and streams it to the gRPC server.
    """
    text_to_say = "노래 듣고 싶어 Spotify 켜줘"
    filename = "test_input.mp3"
    
    print(f"Generating TTS Audio: '{text_to_say}'...")
    tts = gTTS(text=text_to_say, lang='ko')
    tts.save(filename)
    print(f"Audio saved to {filename}")

    # 1. Connect to Server
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = audio_pb2_grpc.SpeechServiceStub(channel)
        print("Connected to gRPC server at localhost:50051")

        # 2. Generator for Streaming Requests
        async def request_generator():
            chunk_size = 1024 * 16 # 16KB chunks
            
            with open(filename, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield audio_pb2.AudioRequest(audio_data=data, is_final=False)
            
            # Send Final Flag
            yield audio_pb2.AudioRequest(audio_data=b'', is_final=True)
            print("Finished sending audio stream.")

        # 3. Call RPC
        try:
            print("Waiting for Server Response (Transcribe + AI)...")
            response = await stub.SendAudioStream(request_generator())
            print("-" * 30)
            print(f"AI Response Text: {response.text}")
            if response.command:
                print(f"Command: {response.command}")
                print(f"Parameter: {response.parameter}")
                print(">> CLIENT ACTION: Executing Command locally...")
            else:
                print("Command: None (Just Chat)")
            print("-" * 30)
        except grpc.RpcError as e:
            print(f"gRPC Error: {e.code()} - {e.details()}")

    # Cleanup
    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    asyncio.run(test_real_audio_stream())
