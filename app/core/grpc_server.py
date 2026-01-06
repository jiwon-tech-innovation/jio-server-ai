"""
gRPC Server for JIAA Intelligence Worker (Dev 5)

Services:
- AudioService: Audio streaming from Dev 1 (기존)
- IntelligenceService: AI operations for Dev 4 (Core Decision Service)
"""
import grpc
import grpc.aio
"""
gRPC Server for JIAA Intelligence Worker (Dev 5)

Services:
- AudioService: Audio streaming from Dev 1 (기존)
- IntelligenceService: AI operations for Dev 4 (Core Decision Service)
"""
import grpc
import grpc.aio
import json
import traceback

from app.protos import audio_pb2, audio_pb2_grpc
from app.services import stt, classifier, chat
from app.schemas.intelligence import ClassifyRequest, ChatRequest, SolveRequest
from app.core.security import get_security_service


class AudioService(audio_pb2_grpc.AudioServiceServicer):
    """Dev 1(OS Agent)과의 오디오 스트리밍 서비스"""
    
    async def TranscribeAudio(self, request_iterator, context):
        """
        Receives AudioStream, aggregates bytes, performs STT -> Chat.
        Matches Dev 1's Proto definition.
        """
        audio_buffer = bytearray()
        final_media_info = {}
        
        try:
            async for request in request_iterator:
                audio_buffer.extend(request.audio_data)
                
                # [DEBUG] Check for media_info_json
                if request.media_info_json:
                    try:
                        # Decrypt JSON if needed? Assuming JSON is separate or part of payload?
                        # Proto definition says `string media_info_json`. Strings are usually sent as-is or base64 if encrypted.
                        # We will assume it's plain text for now unless specified.
                        info = json.loads(request.media_info_json)
                        final_media_info.update(info)
                    except:
                        pass

                if request.is_final:
                    break
        except Exception as e:
            print(f"gRPC Stream Error: {e}")
            traceback.print_exc()

        print(f"🎤 [Server] Audio Received: {len(audio_buffer)} bytes. Context: {final_media_info}")

        # 1. STT
        stt_response = await stt.transcribe_bytes(bytes(audio_buffer), file_ext="mp3")
        user_text = stt_response.text
        
        # 🎤 로그: 사용자가 말한 내용 출력
        print(f"🗣️ [STT] User said: \"{user_text}\"")

        # 2. Chat (Tsundere Response)
        chat_request = ChatRequest(text=user_text)
        chat_response = await chat.chat_with_persona(chat_request)

        # 3. Construct JSON Intent
        intent_data = {
            "text": chat_response.message,
            "state": chat_response.judgment,
            "type": chat_response.intent,
            "command": chat_response.action_code,
            "parameter": chat_response.action_detail or ""
        }
        
        final_intent = json.dumps(intent_data, ensure_ascii=False)

        return audio_pb2.AudioResponse(
            transcript=user_text,
            is_emergency=False,
            intent=final_intent
        )


# =============================================================================
# IntelligenceService - Dev 4 (Core Decision Service) 연동용
# =============================================================================
from app.services import solver


class IntelligenceService:
    """
    Dev 4(Core Decision Service, Go)와 통신하기 위한 gRPC 서비스
    """
    
    async def AnalyzeLog(self, request, context):
        """에러 로그 분석 (Emergency Protocol)"""
        print(f"[IntelligenceService] AnalyzeLog called: client_id={request.client_id}")
        
        try:
            audio_decibel = 95 if request.scream_text else 60
            solve_request = SolveRequest(
                log=request.error_log,
                audio_decibel=audio_decibel
            )
            
            solve_response = await solver.solve_error(solve_request)
            
            markdown = f"""# 🔧 에러 해결 가이드

## 원인 분석
{solve_response.comfort_message}

## 해결 방법
```
{solve_response.solution_code}
```

## 📝 Today I Learned
{solve_response.til_content}
"""
            
            return {
                "success": True,
                "markdown": markdown,
                "solution_code": solve_response.solution_code,
                "error_type": "RUNTIME_ERROR",
                "confidence": 0.85
            }
            
        except Exception as e:
            print(f"[IntelligenceService] AnalyzeLog Error: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "markdown": f"분석 실패: {str(e)}",
                "solution_code": "",
                "error_type": "UNKNOWN",
                "confidence": 0.0
            }
    
    async def ClassifyURL(self, request, context):
        """URL/Title 분류 (Study vs Play)"""
        # Logic remains same
        try:
            classify_request = ClassifyRequest(
                content_type="URL",
                content=request.url if request.url else request.title
            )
            
            classify_response = await classifier.classify_content(classify_request)
            
            classification_map = {
                "STUDY": 1, "PLAY": 2, "NEUTRAL": 3, "WORK": 4, "UNKNOWN": 0
            }
            classification = classification_map.get(classify_response.result, 0)
            
            return {
                "success": True,
                "classification": classification,
                "confidence": classify_response.confidence,
                "reason": classify_response.reason
            }
            
        except Exception as e:
            print(f"[IntelligenceService] ClassifyURL Error: {e}")
            return {
                "success": False,
                "classification": 0,
                "confidence": 0.0,
                "reason": f"분류 실패: {str(e)}"
            }
    
    async def TranscribeAudio(self, request_iterator, context):
        """실시간 STT (스트리밍) - IntelligenceService Version"""
        print("[IntelligenceService] TranscribeAudio stream started")
        
        audio_buffer = bytearray()
        
        try:
            async for chunk in request_iterator:
                audio_buffer.extend(chunk.audio_data)
                if chunk.is_final:
                    break
            
            if len(audio_buffer) == 0:
                print("[IntelligenceService] ⚠️ Received empty audio buffer")
                return {
                    "success": False, "text": "(No audio data)", "is_final": True, "audio_level": 0.0
                }

            stt_response = await stt.transcribe_bytes(bytes(audio_buffer), file_ext="wav")
            print(f"[IntelligenceService] Transcribed: {stt_response.text}")
            
            return {
                "success": True,
                "text": stt_response.text,
                "is_final": True,
                "audio_level": 60.0
            }
            
        except Exception as e:
            print(f"[IntelligenceService] TranscribeAudio Error: {e}")
            return {
                "success": False, "text": f"STT Error: {str(e)}", "is_final": True, "audio_level": 0.0
            }


# =============================================================================
# gRPC Server Setup
# =============================================================================

async def serve_grpc():
    """gRPC 서버 시작 - AudioService + IntelligenceService"""
    server = grpc.aio.server()
    
    # 1. AudioService 등록
    audio_pb2_grpc.add_AudioServiceServicer_to_server(AudioService(), server)
    
    # 2. IntelligenceService 등록
    intelligence_servicer = IntelligenceService()
    
    # 수동으로 서비스 핸들러 등록 (protobuf 의존성 없이)
    from grpc import unary_unary_rpc_method_handler, stream_unary_rpc_method_handler
    
    rpc_method_handlers = {
        'AnalyzeLog': unary_unary_rpc_method_handler(
            intelligence_servicer.AnalyzeLog,
        ),
        'ClassifyURL': unary_unary_rpc_method_handler(
            intelligence_servicer.ClassifyURL,
        ),
        'TranscribeAudio': stream_unary_rpc_method_handler(
            intelligence_servicer.TranscribeAudio,
        ),
    }

    # 3. TrackingService 등록 (New Hybrid Logic + Clipboard Security)
    from app.services.tracking_service import TrackingService
    tracking_servicer = TrackingService()
    
    tracking_rpc_handlers = {
        'SendAppList': unary_unary_rpc_method_handler(
            tracking_servicer.SendAppList,
        ),
        'SendClipboard': unary_unary_rpc_method_handler(
            tracking_servicer.SendClipboard,
        )
    }
    
    generic_handler_tracking = grpc.method_handlers_generic_handler(
        'jiaa.tracking.TrackingService',
        tracking_rpc_handlers
    )
    server.add_generic_rpc_handlers((generic_handler_tracking,))
    
    generic_handler = grpc.method_handlers_generic_handler(
        'jiaa.IntelligenceService', 
        rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))
    
    # 서버 시작
    server.add_insecure_port('[::]:50051')
    print("=" * 50)
    print("gRPC Server running on port 50051")
    print("Services:")
    print("  - AudioService")
    print("  - IntelligenceService")
    print("  - TrackingService (AppList + Secure Clipboard)")
    print("=" * 50)
    
    await server.start()
    await server.wait_for_termination()
