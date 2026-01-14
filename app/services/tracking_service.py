import grpc
import json
import re
from app.protos import tracking_pb2, tracking_pb2_grpc
from app.core.crypto import decrypt_data_raw
from app.services.memory_service import memory_service
from app.core.llm import get_llm, HAIKU_MODEL_ID

class TrackingService(tracking_pb2_grpc.TrackingServiceServicer):
    async def SendAppList(self, request, context):
        try:
            apps = json.loads(request.apps_json)
            # print(f"📱 [Tracking] Received {len(apps)} apps", flush=True)
            
            # Server-side Supplementary Blacklist (Hybrid Logic)
            # 클라이언트에는 없는 게임들을 여기서 잡음
            SERVER_BLACKLIST = ["Overwatch", "MapleStory", "Destiny", "Battle.net", "Steam"]
            
            kill_target = ""
            command = "NONE"
            msg = "OK"
            
            # 1. Check Apps (Hybrid: Blacklist -> AI)
            
            # 1-1. Fast Blacklist Check
            for app in apps:
                for bad in SERVER_BLACKLIST:
                    if bad.lower() in app.lower():
                        kill_target = app
                        command = "KILL"
                        msg = f"서버 감지: {app} 실행이 감지되었습니다. 강제 종료합니다."
                        print(f"🚫 [Tracking] SERVER DETECTED BLACKLIST: {app}")
                        break
                if command == "KILL":
                    break
            
            # 1-2. AI Detection (Claude 3.5 Haiku) - If not already killed
            if command == "NONE":
                try:
                    from app.services import game_detector
                    from app.schemas.game import GameDetectRequest
                    
                    # AI Detect
                    detect_req = GameDetectRequest(apps=apps)
                    ai_result = await game_detector.detect_games(detect_req)
                    
                    if ai_result.is_game_detected:
                        # AI가 게임으로 판단함
                        kill_target = ai_result.target_app
                        command = "KILL"
                        msg = ai_result.message or f"AI 감지: {kill_target} 실행이 확인되었습니다."
                        print(f"🤖 [Tracking] AI DETECTED GAME: {kill_target} (Conf: {ai_result.confidence})")
                except Exception as e:
                    print(f"⚠️ [Tracking] AI Detection Error: {e}")

            
            # 2. Handle Clipboard & Silence (Nagging)
            # Only trigger if NO Kill command is active (Priority: Kill > Nag)
            if command == "NONE" and request.clipboard_payload:
                try:
                    # Decrypt Clipboard
                    clipboard_text = decrypt_data_raw(
                        request.clipboard_payload,
                        request.clipboard_key,
                        request.clipboard_iv,
                        request.clipboard_tag
                    )
                    
                    # Silence Check (e.g., 30 mins = 30.0)
                    # For Demo: Use 1 minute (1.0) or even 0.5
                    silence_min = memory_service.get_silence_duration_minutes()
                    
                    if silence_min > 5.0 and len(clipboard_text.strip()) > 10:
                        print(f"🤐 [Tracking] User Silent for {silence_min:.1f}m. Context: Clipboard")
                        
                        # Generate Nag via LLM
                        llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.7)
                        prompt = f"""
                        You are "Alpine" (Tsundere AI). User is master ("주인님").
                        User has been silent for {int(silence_min)} minutes.
                        However, they just copied this text to clipboard:
                        
                        '''
                        {clipboard_text}
                        '''
                        
                        If this is Code/Error: Scold them for struggling alone or tease them.
                        If this is Chat/Text: Ask who they are talking to.
                        
                        Keep it short (1 sentence). Start with "주인님,".
                        Tone: Cheeky/Nagging.
                        Language: Korean.
                        """
                        response = await llm.ainvoke(prompt)
                        nag_msg = response.content.strip()
                        
                        # Override Command to SPEAK (Client must handle this)
                        command = "SPEAK" 
                        msg = nag_msg
                        
                        # Update interaction time to prevent spamming
                        memory_service.update_interaction_time()
                        
                except Exception as e:
                    print(f"⚠️ [Tracking] Clipboard Error: {e}")

            return tracking_pb2.AppListResponse(
                success=True,
                message=msg,
                command=command,
                target_app=kill_target
            )
        except Exception as e:
            print(f"❌ [Tracking] Service Error: {e}")
            return tracking_pb2.AppListResponse(success=False, message=str(e))
