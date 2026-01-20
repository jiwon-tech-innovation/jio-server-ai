import grpc
import json
import re
from app.protos import tracking_pb2, tracking_pb2_grpc
from app.core.crypto import decrypt_data_raw
from app.services.memory_service import memory_service
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.services import stt, chat
from app.schemas.intelligence import ChatRequest


from app.protos import core_pb2, core_pb2_grpc

class TrackingService(tracking_pb2_grpc.TrackingServiceServicer, core_pb2_grpc.CoreServiceServicer):
    
    def __init__(self):
        self._blacklist_cache = ["Overwatch", "MapleStory", "Destiny", "Battle.net", "Steam", "League of Legends", "Riot Client"]
        self._blacklist_last_updated = 0
        self._blacklist_ttl = 60  # Cache for 60 seconds
    
    # ... (TranscribeAudio remains same) ...

    async def TranscribeAudio(self, request_iterator, context):
        """
        [Highway AI] Streaming Audio Transcription with Real-time AI Response.
        
        Flow:
        1. Receive audio stream from client
        2. Perform STT
        3. Stream AI response chunks back to client for real-time TTS
        """
        audio_buffer = bytearray()
        final_media_info = {}

        try:
            async for request in request_iterator:
                audio_buffer.extend(request.audio_data)
                
                # Validate media_info_json
                if hasattr(request, 'media_info_json') and request.media_info_json:
                    try:
                        info = json.loads(request.media_info_json)
                        final_media_info.update(info)
                    except:
                        pass

                if request.is_final:
                    break
        except Exception as e:
            print(f"gRPC Stream Error: {e}")

        # 1. STT
        stt_response = await stt.transcribe_bytes(bytes(audio_buffer), file_ext="mp3")
        user_text = stt_response.text
        print(f"🗣️ [Highway] User said: \"{user_text}\"")

        if not user_text or not user_text.strip():
            yield tracking_pb2.AudioResponse(
                transcript="(No speech detected)",
                is_emergency=False,
                intent="{}",
                is_partial=False,
                is_complete=True,
                text_chunk="",
                emotion="NORMAL"
            )
            return

        # 2. Stream Chat Response (Highway AI)
        user_id = self._extract_user_from_metadata(context) or "dev1"
        print(f"👤 [Highway] Identified User: {user_id}")
        
        chat_request = ChatRequest(text=user_text, user_id=user_id)
        
        full_text = ""
        final_intent = {}
        
        # Use streaming chat function
        async for text_chunk, is_complete, metadata in chat.chat_with_persona_stream(chat_request):
            if is_complete:
                # Final chunk with intent data
                final_intent = metadata
                intent_data = {
                    "text": full_text,
                    "state": metadata.get("judgment", "NEUTRAL"),
                    "type": metadata.get("intent", "CHAT"),
                    "command": metadata.get("action_code", "NONE"),
                    "parameter": metadata.get("action_detail", ""),
                    "emotion": metadata.get("emotion", "NORMAL")
                }

                # [LOGIC HOOK] Handle Smart Note Generation (TIL)
                # Check BOTH the LLM Intent AND explicit keywords (Override)
                is_til_request = intent_data["command"] == "GENERATE_NOTE"
                
                # Hard Rule: If user says "TIL", "Quiz", "Report", force generation
                if any(k in user_text.lower() for k in ["til", "퀴즈", "quiz", "report", "회고록", "정리해줘"]):
                    print(f"DEBUG: Keyword override triggering TIL Generation for: {user_text}")
                    is_til_request = True

                if is_til_request:
                    # [FIX] Robust Parameter Handling: Strip whitespace and default to Daily_Report
                    topic = (intent_data["parameter"] or "").strip()
                    if not topic or topic.lower() == "summary":
                         topic = "Daily_Report"
                    
                    print(f"DEBUG: Generating Note for topic: {topic}")
                    
                    try:
                        # Generate Content
                        markdown_content = await memory_service.get_recent_summary_markdown(topic, user_id=user_id)
                        
                        # Mutate Response to WRITE_FILE for Client
                        intent_data["command"] = "WRITE_FILE"
                        valid_filename = f"{topic.replace(' ', '_')}_Note.md"
                        intent_data["parameter"] = valid_filename
                        intent_data["message"] = markdown_content
                        # [FIX] Clear "text" field so Client doesn't accidentally use spoken text as content
                        intent_data["text"] = "" 
                        
                        print(f"DEBUG: 📝 Generated Note (Len: {len(markdown_content)}). Sending WRITE_FILE.")
                    except Exception as e:
                        print(f"⚠️ [Tracking] TIL Generation Failed: {e}")
                        intent_data["command"] = "CHAT"
                        intent_data["message"] = f"보고서 생성 중 오류가 발생했습니다: {e}"
                        # Ensure text (spoken) is preserved in error case so user hears "I'm sorry..."
                    
                    # Ensure text (spoken) is preserved, content is in message
                
                yield tracking_pb2.AudioResponse(
                    transcript=user_text,
                    is_emergency=False,
                    intent=json.dumps(intent_data, ensure_ascii=False),
                    is_partial=False,
                    is_complete=True,
                    text_chunk="",
                    emotion=intent_data["emotion"]
                )
            else:
                # Partial chunk for TTS
                full_text += text_chunk
                yield tracking_pb2.AudioResponse(
                    transcript="",
                    is_emergency=False,
                    intent="",
                    is_partial=True,
                    is_complete=False,
                    text_chunk=text_chunk,
                    emotion=metadata.get("emotion", "NORMAL")
                )


    def _extract_user_from_metadata(self, context) -> str:
        """
        Extract user_id (email) from gRPC metadata (Authorization: Bearer <token>)
        """
        try:
            metadata = dict(context.invocation_metadata())
            token = metadata.get("authorization", "")
            
            if not token:
                # Also check lowercase
                for k, v in metadata.items():
                    if k.lower() == "authorization":
                        token = v
                        break
            
            if token and token.startswith("Bearer "):
                jwt_str = token.split("Bearer ")[1]
                # Decode Payload (2nd part)
                parts = jwt_str.split(".")
                if len(parts) >= 2:
                    payload_b64 = parts[1]
                    # Fix padding
                    payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                    
                    import base64
                    decoded_bytes = base64.b64decode(payload_b64)
                    payload_json = json.loads(decoded_bytes)
                    
                    # Try 'sub' (Standard) or 'email' (Custom)
                    user_id = payload_json.get("sub") or payload_json.get("email")
                    if user_id:
                        return user_id
        except Exception as e:
            print(f"⚠️ [Tracking] Failed to extract identity: {e}")
        
        return None

    async def SyncClient(self, request_iterator, context):
        """
        Bidirectional Stream for Client Heartbeat (CoreService).
        Handles Game Detection & Nagging.
        """
        user_id = self._extract_user_from_metadata(context) or "dev1"
        print(f"⚡ [Core] SyncClient Connected. User: {user_id}")
        
        # [UPDATED] Fetch from Data Server (Admin Page) with Caching
        SERVER_BLACKLIST = await self._get_blacklist()
        # Fallback to hardcoded if empty (network error on init)
        if not SERVER_BLACKLIST:
             SERVER_BLACKLIST = ["Overwatch", "MapleStory", "Destiny", "Battle.net", "Steam", "League of Legends", "Riot Client"]

        
        try:
            async for heartbeat in request_iterator:
                # 1. Parse Apps
                apps = []
                if heartbeat.apps_json:
                    try:
                        apps = json.loads(heartbeat.apps_json)
                    except:
                        pass
                
                # Skip detection if app list is empty
                if not apps:
                    continue

                kill_target = ""
                command_type = core_pb2.ServerCommand.NONE
                payload = ""

                # 2. Hybrid Game Detection
                
                # 2-1. Fast Blacklist
                for app in apps:
                    for bad in SERVER_BLACKLIST:
                        if bad.lower() in app.lower():
                            kill_target = app
                            command_type = core_pb2.ServerCommand.KILL_PROCESS
                            payload = app
                            print(f"🚫 [Core] BLACKLIST DETECTED: {app}")
                            break
                    if command_type != core_pb2.ServerCommand.NONE:
                        break
                
                # 2-2. AI Detection (If no blacklist hit)
                # [Wall 2 -> Wall 3 Logic]
                # Trigger AI Judge ONLY if input patterns are suspicious (Gaming-like)
                # 1. Low Entropy Typing: Gaming usually uses limited keys (WASD, QWER) -> Low Entropy (< 3.0)
                #    Productive work (Coding/Chatting) uses full keyboard -> High Entropy (> 4.0)
                # 2. High Mouse Activity: Spam clicks (>10/s) or frantic movement (>1000px/s) usually means RTS/FPS.
                
                h = heartbeat
                is_suspicious_input = False
                
                # Case A: Suspicious Keyboard (Repetitive Keys)
                if h.keystroke_count > 5 and h.keyboard_entropy < 3.0:
                    is_suspicious_input = True
                    # print(f"🔍 [Wall 2] Suspicious Keyboard: Count={h.keystroke_count}, Entropy={h.keyboard_entropy:.2f}")
                
                # Case B: High Mouse Activity (LoL/FPS)
                elif h.click_count > 10 or h.mouse_distance > 1000:
                    is_suspicious_input = True
                    # print(f"🔍 [Wall 2] Suspicious Mouse: Clicks={h.click_count}, Dist={h.mouse_distance}")

                # Case C: Active Blacklist Check fallback (Input exists but not suspicious? Maybe just check anyway if we want strictness)
                # User asked for "Suspicious" trigger.
                # If I am just browsing (scroll, low click, no keys), entropy is 0. 
                # Let's verify: If keys=0, entropy=0. 
                # My logic: active_keys > 5. So passive browsing is IGNORED.
                
                if command_type == core_pb2.ServerCommand.NONE and is_suspicious_input:
                    try:
                        # Throttle AI checks? (Maybe doing it every heartbeat is too much?)
                        # But heartbeat is 1s. Let's rely on GameDetector being fast or create a cache if needed.
                        # For now, let's call it.
                        from app.services import game_detector
                        from app.schemas.game import GameDetectRequest
                        
                        detect_req = GameDetectRequest(apps=apps)
                        ai_result = await game_detector.detect_games(detect_req)
                        
                        if ai_result.is_game_detected:
                            kill_target = ai_result.target_app
                            command_type = core_pb2.ServerCommand.KILL_PROCESS
                            payload = kill_target
                            msg = ai_result.message
                            
                            # Also send a MESSAGE to scold user?
                            # Current protocol only supports one command per heartbeat response? 
                            # Or we can yield multiple.
                            
                            print(f"🤖 [Core] AI DETECTED GAME: {kill_target}")
                            
                            # Yield Message First
                            if msg:
                                yield core_pb2.ServerCommand(
                                    type=core_pb2.ServerCommand.SHOW_MESSAGE,
                                    payload=msg
                                )

                    except Exception as e:
                        print(f"⚠️ [Core] AI Error: {e}")

                # 3. Yield Command
                if command_type != core_pb2.ServerCommand.NONE:
                    # [FIX] Log Game Detection to Data Service
                    if command_type == core_pb2.ServerCommand.KILL_PROCESS:
                         await self._log_game_detection(payload, "BLACKLIST_CoRE" if "AI" not in payload else "AI_JUDGE", user_id)

                    yield core_pb2.ServerCommand(
                        type=command_type,
                        payload=payload
                    )
        
        except Exception as e:
            print(f"❌ [Core] SyncClient Disconnected OR Stream Ended: {e}")

    async def _log_game_detection(self, app_name: str, detection_source: str, user_id: str):
        """
        Log detected game to Data Service (InfluxDB)
        """
        try:
            import httpx
            # Internal Cluster URL for Data Service
            url = "http://jiaa-server-data.jiaa.svc.cluster.local:8082/api/v1/log"
            
            payload = {
                "user_id": user_id, 
                "category": "PLAY", 
                "type": "GAME_DETECTED",
                "data": {
                    "app_name": app_name,
                    "source": detection_source,
                    "action": "KILL_PROCESS"
                },
                "timestamp": int(time.time() * 1000)
            }
            
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    print(f"✅ [Core] Game Logged: {app_name}")
                else:
                    print(f"⚠️ [Core] Failed to log game: {resp.status_code}")
                    
        except Exception as e:
            print(f"⚠️ [Core] Logging Error: {e}")
            pass

    async def SendAppList(self, request, context):
        # ... (Legacy Implementation or just redirect) ...
        return tracking_pb2.AppListResponse(success=True, message="Deprecated. Use SyncClient.")

    async def _get_blacklist(self):
        """
        Fetch blacklist from Data Service with caching
        """
        import time
        import httpx

        now = time.time()
        if now - self._blacklist_last_updated < self._blacklist_ttl:
            return self._blacklist_cache

        try:
            # Internal Cluster URL for Data Service
            url = "http://jiaa-server-data.jiaa.svc.cluster.local:8082/api/v1/blacklist"
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    # Extract appName from list of objects
                    new_list = [item["appName"] for item in data if item.get("appName")]
                    
                    if new_list:
                        self._blacklist_cache = new_list
                        self._blacklist_last_updated = now
                        # print(f"🔄 [Tracking] Blacklist Updated: {len(new_list)} items")
                    
                    return self._blacklist_cache
        except Exception as e:
            print(f"⚠️ [Tracking] Failed to fetch blacklist: {e}")
        
        return self._blacklist_cache

    async def ReportAnalysisResult(self, request, context):
        print(f"📊 [Core] Analysis Report: {request.type}")
        return core_pb2.Ack(success=True)
