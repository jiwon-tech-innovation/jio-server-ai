"""
gRPC Server for JIAA Intelligence Worker (Dev 5)

Services:
- AudioService: Audio streaming from Dev 1 (기존)
- IntelligenceService: AI operations for Dev 4 (Core Decision Service)
"""
import grpc
from concurrent import futures
import grpc.aio
import json
from grpc_health.v1 import health
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc

from app.protos import audio_pb2, audio_pb2_grpc
from app.services import stt, classifier, chat
from app.schemas.intelligence import ClassifyRequest, ChatRequest, SolveRequest
from app.core.kafka import kafka_producer
from app.core.config import get_settings
from grpc_health.v1 import health
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc

settings = get_settings()


class AudioService(audio_pb2_grpc.AudioServiceServicer):
    """Dev 1(OS Agent)과의 오디오 스트리밍 서비스"""
    
    async def TranscribeAudio(self, request_iterator, context):
        """
        Receives AudioStream, aggregates bytes, performs STT -> Chat.
        Matches Dev 1's Proto definition.
        """
        audio_buffer = bytearray()
        
        # Context Accumulator
        final_media_info = {}

        try:
            async for request in request_iterator:
                audio_buffer.extend(request.audio_data)
                
                # [DEBUG] Check for media_info_json
                if request.media_info_json:
                    try:
                        info = json.loads(request.media_info_json)
                        final_media_info.update(info)
                        print(f"✅ [Server] Updated Media Info: {info.keys()}")
                    except:
                        pass

                if request.is_final:
                    break
        except Exception as e:
            print(f"gRPC Stream Error: {e}")

        print(f"🎤 [Server] Audio Received: {len(audio_buffer)} bytes. Context: {final_media_info}")

        # 1. STT
        import time
        start_stt = time.time()
        stt_response = await stt.transcribe_bytes(bytes(audio_buffer), file_ext="mp3")
        stt_duration = time.time() - start_stt
        print(f"⏱️ [Perf] STT Duration: {stt_duration:.2f}s")
        
        user_text = stt_response.text
        
        # 🎤 로그: 사용자가 말한 내용 출력
        print(f"🗣️ [STT] User said: \"{user_text}\"")

        # 1-1. Empty Check (Prevent Bedrock Error)
        if not user_text or not user_text.strip():
            print("[Server] Empty transcription, skipping AI.")
            return audio_pb2.AudioResponse(
                transcript="(No speech detected)",
                is_emergency=False,
                intent="{}"
            )

        # 2. Chat (Tsundere Response)
        # Extract user_id from accumulated media_info or default to dev1
        user_id = final_media_info.get("user_id", "dev1")
        print(f"👤 [Audio] Chatting as User: {user_id}")
        # Pass running apps context if available for game detection
        user_text_with_context = user_text
        running_apps_list = []
        if final_media_info.get("windows"):
            try:
                windows = final_media_info["windows"]
                if isinstance(windows, list) and len(windows) > 0:
                    # Extract app names (remove browser titles like "Google Chrome - [title]")
                    running_apps_list = []
                    for app in windows[:20]:  # Limit to first 20 apps
                        # Remove browser title suffixes
                        app_name = app.split(" - ")[0].strip()
                        if app_name and app_name not in running_apps_list:
                            running_apps_list.append(app_name)
                    
                    # Add context about running apps to help identify games
                    apps_context = ", ".join(running_apps_list)
                    user_text_with_context = f"{user_text} [현재 실행 중인 앱: {apps_context}]"
                    print(f"📱 [Context] Running apps ({len(running_apps_list)}): {apps_context[:100]}...")
            except Exception as e:
                print(f"⚠️ [Context] Failed to parse windows: {e}")
        
        chat_request = ChatRequest(text=user_text_with_context, user_id=user_id)
        chat_response = await chat.chat_with_persona(chat_request)

        # 3. Construct JSON Intent (스키마에 맞게 매핑)
        # 3. Construct JSON Intent (스키마에 맞게 매핑)
        intent_data = {
            "text": chat_response.message,           # message → text
            "state": chat_response.judgment,        # judgment (STUDY/PLAY/NEUTRAL)
            "type": chat_response.intent,           # intent (COMMAND/CHAT)
            "command": chat_response.action_code,   # action_code (OPEN_APP, etc.)
            "parameter": chat_response.action_detail or "",  # action_detail
            "emotion": chat_response.emotion or "NORMAL"    # emotion tag
        }
        
        # [Multi-Command Support]
        if chat_response.multi_actions:
            print(f"🚀 [gRPC] Forwarding Multi-Actions: {len(chat_response.multi_actions)} items")
            final_intent = json.dumps(chat_response.multi_actions, ensure_ascii=False)
        else:
            final_intent = json.dumps(intent_data, ensure_ascii=False)

        # 4. [Integrations] Send to Kafka (Dev 4)
        if intent_data["type"] == "COMMAND" or intent_data["state"] in ["STUDY", "PLAY"]:
            print(f"🚀 [gRPC] Forwarding Decision to Kafka: {settings.KAFKA_TOPIC_AI_INTENT}")
            await kafka_producer.send_message(settings.KAFKA_TOPIC_AI_INTENT, intent_data)

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
    
    Methods:
    - AnalyzeLog: 에러 로그 분석 (Emergency Protocol)
    - ClassifyURL: URL/Title을 STUDY vs PLAY로 분류
    - TranscribeAudio: 실시간 STT (스트리밍)
    """
    
    async def AnalyzeLog(self, request, context):
        """
        에러 로그 분석 (Emergency Protocol)
        
        Dev 6가 EMERGENCY 상태 전송 시, Dev 4가 이 메서드를 호출
        """
        print(f"[IntelligenceService] AnalyzeLog called: client_id={request.client_id}")
        print(f"[IntelligenceService] ErrorLog length: {len(request.error_log)}")
        print(f"[IntelligenceService] ScreamText: {request.scream_text}")
        
        try:
            # SolveRequest 생성 (audio_decibel은 비명 텍스트 유무로 판단)
            audio_decibel = 95 if request.scream_text else 60
            solve_request = SolveRequest(
                log=request.error_log,
                audio_decibel=audio_decibel
            )
            
            # solver.py의 solve_error 호출
            solve_response = await solver.solve_error(solve_request)
            
            # Markdown 형태로 결과 조합
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
            
            # 응답 생성 - 딕셔너리로 반환 (순수 Python 객체)
            return {
                "success": True,
                "markdown": markdown,
                "solution_code": solve_response.solution_code,
                "error_type": "RUNTIME_ERROR",
                "confidence": 0.85
            }
            
        except Exception as e:
            print(f"[IntelligenceService] AnalyzeLog Error: {e}")
            return {
                "success": False,
                "markdown": f"분석 실패: {str(e)}",
                "solution_code": "",
                "error_type": "UNKNOWN",
                "confidence": 0.0
            }
    
    async def ClassifyURL(self, request, context):
        """
        URL/Title 분류 (Study vs Play)
        
        Dev 4가 실시간 블랙리스트 판단에 사용
        """
        print(f"[IntelligenceService] ClassifyURL called: url={request.url}, title={request.title}")
        
        try:
            # classifier.py의 classify_content 호출
            classify_request = ClassifyRequest(
                content_type="URL",
                content=request.url if request.url else request.title
            )
            
            classify_response = await classifier.classify_content(classify_request)
            
            # URLClassification enum 매핑
            classification_map = {
                "STUDY": 1,
                "PLAY": 2,
                "NEUTRAL": 3,
                "WORK": 4,
                "UNKNOWN": 0
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
        """
        실시간 STT (스트리밍)
        
        Dev 4가 오디오 스트림을 전송하면 텍스트로 변환
        """
        print("[IntelligenceService] TranscribeAudio stream started")
        
        audio_buffer = bytearray()
        client_id = ""
        
        try:
            async for chunk in request_iterator:
                client_id = chunk.client_id
                audio_buffer.extend(chunk.audio_data)
                if chunk.is_final:
                    break
            
            # STT 수행
            if len(audio_buffer) == 0:
                print("[IntelligenceService] ⚠️ Received empty audio buffer")
                return {
                    "success": False,
                    "text": "(No audio data)",
                    "is_final": True,
                    "audio_level": 0.0
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
                "success": False,
                "text": f"STT Error: {str(e)}",
                "is_final": True,
                "audio_level": 0.0
            }


# =============================================================================
# gRPC Server Setup
# =============================================================================

def _create_method_handlers(servicer):
    """IntelligenceService용 메서드 핸들러 생성"""
    return {
        'AnalyzeLog': grpc.unary_unary_rpc_method_handler(
            servicer.AnalyzeLog,
        ),
        'ClassifyURL': grpc.unary_unary_rpc_method_handler(
            servicer.ClassifyURL,
        ),
        'TranscribeAudio': grpc.stream_unary_rpc_method_handler(
            servicer.TranscribeAudio,
        ),
    }


class IntelligenceServiceHandler(grpc.aio.ServicerContext):
    """간단한 gRPC 핸들러 (protobuf 없이 동작)"""
    
    def __init__(self, servicer):
        self.servicer = servicer
    
    async def handle_analyze_log(self, request_data):
        """AnalyzeLog RPC 핸들러"""
        class Request:
            def __init__(self, data):
                self.client_id = data.get("client_id", "")
                self.error_log = data.get("error_log", "")
                self.scream_text = data.get("scream_text", "")
                self.context = data.get("context", "")
        
        return await self.servicer.AnalyzeLog(Request(request_data), None)


async def serve_grpc():
    """gRPC 서버 시작 - AudioService + IntelligenceService"""
    server = grpc.aio.server()
    
    # 1. AudioService 등록 (기존) - REMOVED (Consolidated into TrackingService)
    # audio_pb2_grpc.add_AudioServiceServicer_to_server(AudioService(), server)
    print("✅ [Server] AudioService is now handled by TrackingService")
    
    # 2. IntelligenceService 등록
    intelligence_servicer = IntelligenceService()
    
    # 2-1. Health Service 등록 (AWS ALB Support)
    health_servicer = health.HealthServicer(
        experimental_non_blocking=True,
        experimental_thread_pool=futures.ThreadPoolExecutor(max_workers=1)
    )
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    
    # Set Serving Status
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set("jiaa.IntelligenceService", health_pb2.HealthCheckResponse.SERVING)
    print("✅ [gRPC] Health Service Registered (ALB Ready)")
    
    # 수동으로 서비스 핸들러 등록 (protobuf 의존성 없이)
    from grpc import unary_unary_rpc_method_handler, stream_unary_rpc_method_handler, stream_stream_rpc_method_handler
    
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

    # 3. TrackingService 등록 (New Hybrid Logic)
    from app.services.tracking_service import TrackingService
    tracking_servicer = TrackingService()
    
    tracking_rpc_handlers = {
        'SendAppList': unary_unary_rpc_method_handler(
            tracking_servicer.SendAppList,
        ),
        'TranscribeAudio': stream_stream_rpc_method_handler(
            tracking_servicer.TranscribeAudio,
        )
    }
    
    generic_handler_tracking = grpc.method_handlers_generic_handler(
        'jiaa.tracking.TrackingService',
        tracking_rpc_handlers
    )
    server.add_generic_rpc_handlers((generic_handler_tracking,))
    
    # [FIX] Also register as 'jiaa.audio.AudioService' because client uses audio.proto
    # We use an Adapter to bridge audio_pb2 types to tracking_pb2 logic
    
    class AudioServiceAdapter(audio_pb2_grpc.AudioServiceServicer):
        def __init__(self, tracking_svc):
            self.tracking = tracking_svc
            
        async def TranscribeAudio(self, request_iterator, context):
            # [Highway AI] TranscribeAudio now returns a STREAM of responses
            # We need to iterate and yield each response
            
            async for tracking_resp in self.tracking.TranscribeAudio(request_iterator, context):
                # Convert tracking_pb2.AudioResponse -> audio_pb2.AudioResponse
                # Note: audio_pb2.AudioResponse may not have is_partial, is_complete fields
                # We pass what we can
                yield audio_pb2.AudioResponse(
                    transcript=tracking_resp.transcript,
                    is_emergency=tracking_resp.is_emergency,
                    intent=tracking_resp.intent
                )

    # Register the Adapter via standard generated method (handles serialization automatically)
    audio_adapter = AudioServiceAdapter(tracking_servicer)
    audio_pb2_grpc.add_AudioServiceServicer_to_server(audio_adapter, server)
    print("✅ [Audio] AudioServiceAdapter Registered (Bridging Audio -> Tracking)")
    
    # audio_rpc_handlers = {
    #     'TranscribeAudio': stream_unary_rpc_method_handler(
    #         tracking_servicer.TranscribeAudio,
    #     )
    # }
    # generic_handler_audio = grpc.method_handlers_generic_handler(
    #     'jiaa.audio.AudioService',
    #     audio_rpc_handlers
    # )
    # server.add_generic_rpc_handlers((generic_handler_audio,))
    
    # [FIX] Register CoreService for Dev 3 (Game Detection)
    from app.protos import core_pb2_grpc
    # tracking_servicer now implements CoreServiceServicer
    core_pb2_grpc.add_CoreServiceServicer_to_server(tracking_servicer, server)
    print("✅ [Core] CoreService Registered (SyncClient Ready)")

    
    # 4. TextAIService 등록 (New Goal Planner)
    from app.protos import text_ai_pb2, text_ai_pb2_grpc
    from app.services import planner
    
    class TextAIService(text_ai_pb2_grpc.TextAIServiceServicer):
        async def GenerateSubgoals(self, request, context):
            print(f"📝 [Planner] Generating subgoals for: {request.goal_text}")
            subgoals = await planner.generate_subgoals(request.goal_text)
            print(f"✅ [Planner] Result: {subgoals}")
            return text_ai_pb2.GoalResponse(subgoals=subgoals)

        async def Chat(self, request, context):
            print(f"💬 [TextAI] Chat Request from {request.client_id}: {request.text}")
            from app.schemas.intelligence import ChatRequest as SchemaChatRequest
            
            chat_req = SchemaChatRequest(text=request.text, user_id=request.client_id)
            chat_res = await chat.chat_with_persona(chat_req)
            
            return text_ai_pb2.ChatResponse(
                message=chat_res.message,
                intent=chat_res.intent,
                action_code=chat_res.action_code,
                action_detail=chat_res.action_detail,
                emotion=chat_res.emotion,
                judgment=chat_res.judgment
            )

        async def GenerateQuiz(self, request, context):
            print(f"🧠 [Quiz] Generating Quiz: {request.topic} ({request.difficulty})")
            
            # Call planner.generate_quiz
            # Note: generate_quiz returns List[dict] (SubgoalQuiz dictionaries)
            subgoal_quiz_dicts = await planner.generate_quiz(request.topic, request.difficulty)
            
            pb_items = []
            for sg in subgoal_quiz_dicts:
                # Map nested quizzes
                pb_quizzes = []
                for q in sg["quizzes"]:
                    pb_quizzes.append(text_ai_pb2.QuizItem(
                        question=q["question"],
                        options=q["options"],
                        answer=q["answer"], # String answer
                        explanation=q["explanation"]
                    ))
                
                # Create SubgoalQuiz message
                pb_items.append(text_ai_pb2.SubgoalQuiz(
                    subgoal=sg["subgoal"],
                    quizzes=pb_quizzes
                ))
            
            print(f"✅ [Quiz] Generated {len(pb_items)} subgoal groups")
            return text_ai_pb2.QuizResponse(items=pb_items)

    text_ai_servicer = TextAIService()
    
    # Register purely via add_TextAIServiceServicer_to_server if using standard flow
    # or generic handler like others. Let's use the standard way if generated code allows,
    # but based on previous pattern, we might want generic handler if reflection is issues.
    # However, standard way is cleaner.
    text_ai_pb2_grpc.add_TextAIServiceServicer_to_server(text_ai_servicer, server)

    # generic_handler = grpc.method_handlers_generic_handler(
    #     'jiaa.IntelligenceService', 
    #     rpc_method_handlers
    # )
    # server.add_generic_rpc_handlers((generic_handler,))
    
    # Register IntelligenceService handlers (Dev 4)
    # Re-using the dictionary defined above
    generic_handler_intel = grpc.method_handlers_generic_handler(
         'jiaa.IntelligenceService', 
         rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler_intel,))
    
    # 5. [CRITICAL] Standard Health Check Service for AWS ALB
    health_servicer = health.HealthServicer(
        experimental_non_blocking=True,
        experimental_thread_pool=None
    )
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    
    # Mark all services as SERVING
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set("jiaa.IntelligenceService", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set("jiaa.AudioService", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set("jiaa.tracking.TrackingService", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set("jiaa.text_ai.TextAIService", health_pb2.HealthCheckResponse.SERVING)

    
    # 서버 시작
    server.add_insecure_port('[::]:50051')
    print("=" * 50)
    print("gRPC Server running on port 50051")
    print("Services:")
    print("  - AudioService (Dev 1 → Dev 5)")
    print("  - IntelligenceService (Dev 4 → Dev 5)")
    print("  - TrackingService (Dev 6 → Dev 5)")
    print("  - TextAIService (Client → Dev 5)")
    print("=" * 50)
    
    await server.start()
    await server.wait_for_termination()
