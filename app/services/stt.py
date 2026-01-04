import os
import uuid
import time
import asyncio
import json
import boto3
import requests
from fastapi import UploadFile
from app.schemas.intelligence import STTResponse
from app.core.config import get_settings

settings = get_settings()

async def transcribe_audio(file: UploadFile) -> STTResponse:
    """
    HTTP Wrapper: Transcribes UploadFile.
    """
    file_content = await file.read()
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else "mp3"
    return await transcribe_bytes(file_content, file_ext)

def create_wav_header(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """
    Create WAV header for raw PCM data.
    Dev 1 sends 16kHz mono 16-bit PCM.
    """
    import struct
    
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
    Core Logic: Uploads bytes to S3 and calls Transcribe.
    """
    try:
        bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
        if not bucket_name:
            return STTResponse(text="Configuration Error: AWS_S3_BUCKET_NAME is missing.")

        # 🔧 Raw PCM을 WAV로 변환 (Dev 1은 16kHz mono PCM으로 전송)
        if file_ext in ["raw", "pcm", "mp3"]:  # mp3는 실제로 raw PCM임
            file_content = create_wav_header(file_content, sample_rate=16000, channels=1, bits_per_sample=16)
            file_ext = "wav"
            print(f"[STT] Converted raw PCM to WAV ({len(file_content)} bytes)")
        
        # 🔧 오디오 길이 체크 (최소 0.5초 = 16000 samples = 32000 bytes)
        audio_bytes = len(file_content) - 44 if file_ext == "wav" else len(file_content)
        duration_seconds = audio_bytes / 32000  # 16kHz * 2 bytes
        if duration_seconds < 0.5:
            print(f"[STT] ⚠️ Audio too short: {duration_seconds:.2f}s (min 0.5s). Skipping.")
            return STTResponse(text="(오디오가 너무 짧음)")

        s3_client = boto3.client(
            's3',
            region_name=settings.AWS_S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        transcribe_client = boto3.client(
            'transcribe',
            region_name=settings.AWS_S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        job_name = f"jiaa-stt-{uuid.uuid4()}"
        s3_key = f"temp-audio/{job_name}.{file_ext}"

        # 1. Upload to S3
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=file_content)

        job_uri = f"s3://{bucket_name}/{s3_key}"

        # 2. Start Transcription Job
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_uri},
            MediaFormat=file_ext if file_ext in ['mp3', 'mp4', 'wav', 'flac'] else 'wav',
            LanguageCode='ko-KR'
        )

        # 3. Poll for Completion
        while True:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status in ['COMPLETED', 'FAILED']:
                break
            
            await asyncio.sleep(1)

        if job_status == 'COMPLETED':
            # 4. Get Result
            transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
            response = requests.get(transcript_uri)
            data = response.json()
            transcript_text = data['results']['transcripts'][0]['transcript']
            
            # 🎤 Log the received voice transcription
            print(f"[STT] 🎤 Received Voice: \"{transcript_text}\"")
            
            # s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
            return STTResponse(text=transcript_text)
        else:
            return STTResponse(text="Transcription Failed at AWS side.")

    except Exception as e:
        print(f"AWS Transcribe Error: {e}")
        return STTResponse(text=f"Error: {str(e)}")
