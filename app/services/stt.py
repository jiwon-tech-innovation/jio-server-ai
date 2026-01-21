import os
import io
import struct
from fastapi import UploadFile
from groq import AsyncGroq
from app.schemas.intelligence import STTResponse
from app.core.config import get_settings

settings = get_settings()

# Initialize Groq Client (Lazy)
_client_instance = None

def get_groq_client():
    global _client_instance
    if _client_instance:
        return _client_instance
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[STT] ⚠️ GROQ_API_KEY not found. Helper will fail if called.")
        return None
        
    _client_instance = AsyncGroq(
        api_key=api_key,
        timeout=10.0
    )
    return _client_instance

async def transcribe_audio(file: UploadFile) -> STTResponse:
    """
    HTTP Wrapper: Transcribes UploadFile using Groq Whisper.
    """
    try:
        file_content = await file.read()
        # file.filename might be empty or blob
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else "mp3"
        
        return await transcribe_bytes(file_content, file_ext)
    except Exception as e:
        print(f"❌ Transcribe Upload Error: {e}")
        return STTResponse(text="")

def create_wav_header(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """
    Create WAV header for raw PCM data.
    Dev 1 sends 16kHz mono 16-bit PCM.
    """
    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    wav_header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                    # ChunkID
        36 + data_size,             # ChunkSize
        b'WAVE',                    # Format
        b'fmt ',                    # Subchunk1ID
        16,                         # Subchunk1Size (PCM)
        1,                          # AudioFormat (PCM = 1)
        channels,                   # NumChannels
        sample_rate,                # SampleRate
        byte_rate,                  # ByteRate
        block_align,                # BlockAlign
        bits_per_sample,            # BitsPerSample
        b'data',                    # Subchunk2ID
        data_size                   # Subchunk2Size
    )
    
    return wav_header + pcm_data

async def transcribe_bytes(file_content: bytes, file_ext: str = "mp3") -> STTResponse:
    """
    Core Logic: Calls Groq Whisper API.
    """
    if client is None:
        print("❌ STT Error: Groq client not initialized. Please set GROQ_API_KEY environment variable.")
        return STTResponse(text="")
    
    try:
        # 🔧 Handle Raw PCM (Dev 1 Source)
        # OpenAI/Groq Whisper expects a file with a header (wav, mp3, etc.)
        if file_ext in ["raw", "pcm", "mp3"]: # 'mp3' might be mislabeled raw data from some clients
             # Optimization: Check if it already has a RIFF header? 
             # For now, trust the logic: if generic name, assume raw PCM from Dev 1
             if not file_content.startswith(b'RIFF'):
                 file_content = create_wav_header(file_content, sample_rate=16000, channels=1, bits_per_sample=16)
                 file_ext = "wav"
                 # print(f"[STT] Converted raw PCM to WAV ({len(file_content)} bytes)")

        # 🔧 Duration Check
        audio_bytes = len(file_content)
        # Approx duration for 16khz 16bit mono = 32000 bytes/sec
        duration_seconds = audio_bytes / 32000
        if duration_seconds < 0.3: # Increase threshold to reduce noise triggers
             print(f"[STT] ⚠️ Audio too short: {duration_seconds:.2f}s. Skipping.")
             return STTResponse(text="")

        # Create a file-like object
        audio_file = io.BytesIO(file_content)
        audio_file.name = f"voice.{file_ext}" # OpenAI/Groq needs a filename

        print(f"[STT] Calling Groq Whisper... ({duration_seconds:.2f}s)")
        
        # Lazy Init Client
        client = get_groq_client()
        if not client:
             print("[STT] ❌ Cannot transcribe: GROQ_API_KEY missing.")
             return STTResponse(text="")

        transcript = await client.audio.transcriptions.create(
            model="whisper-large-v3", # 🚀 Changed to Groq model
            file=audio_file,
            language="ko", # Force Korean as per spec
            prompt="VSCode, Chrome, Youtube, Study mode, Play mode, AI, 코딩, 개발, 유튜브, 롤, 알았어", 
            temperature=0.0,
            response_format="json"
        )
        
        transcript_text = transcript.text
        print(f"[STT] 🎤 Received Voice (Groq): \"{transcript_text}\"")
        
        return STTResponse(text=transcript_text)

    except Exception as e:
        print(f"❌ Groq Whisper Error: {e}")
        return STTResponse(text="")
