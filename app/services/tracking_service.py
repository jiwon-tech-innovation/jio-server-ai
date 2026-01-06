import grpc
import json
from app.protos import tracking_pb2, tracking_pb2_grpc
from app.core.config import get_settings
from app.core.kafka import kafka_producer

class TrackingService(tracking_pb2_grpc.TrackingServiceServicer):
    # Dynamic Memory for AI Learning
    SERVER_BLACKLIST = ["Overwatch", "MapleStory", "Destiny", "Battle.net", "Steam", "steam_osx", "LoL"]
    KNOWN_SAFE_APPS = {"Google Chrome", "Code", "Finder", "WindowServer", "KakaoTalk", "Slack", "Discord", "iTerm2"}

    async def _analyze_clipboard(self, text: str) -> dict:
        """
        Asks AI to analyze the clipboard content and return a summary.
        """
        try:
            if not text or len(text) < 2: 
                return {"type": "EMPTY", "summary": "Empty"}
                
            from app.core.llm import get_llm, HAIKU_MODEL_ID
            from langchain_core.prompts import PromptTemplate
            
            llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.0)
            
            # Truncate for cost saving if too long (analyzing first 2000 chars is enough)
            preview = text[:2000]
            
            prompt = PromptTemplate.from_template("""
            Analyze this clipboard text and return a JSON summary.
            
            Text: "{text}"
            
            Output JSON:
            {{
                "type": "CODE | ERROR | CHAT | PASSWORD | URL | ETC",
                "summary": "Short 3-5 word summary of what this is (e.g. 'Python Asyncio Error', 'AWS Credentials', 'Funny Meme')",
                "is_sensitive": true/false
            }}
            Only JSON.
            """)
            
            chain = prompt | llm
            res = await chain.ainvoke({"text": preview})
            
            # Simple parsing (assuming model is good enough to return JSON)
            import json
            content = res.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            return json.loads(content)
            
        except Exception as e:
            # print(f"AI Analysis Error: {e}")
            return {"type": "ERROR", "summary": "Analysis Failed"}

    def _decrypt_clipboard(self, enc_payload_b64: str, enc_key_b64: str) -> str:
        """
        Decrypts Hybrid Encrypted Payload.
        1. Decrypt AES Key using Server's RSA Private Key.
        2. Decrypt Payload using AES-GCM.
        """
        import base64
        import os
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        
        # Lazy Load Private Key
        if not hasattr(self, "_private_key"):
            try:
                with open("server_private.pem", "rb") as key_file:
                    self._private_key = serialization.load_pem_private_key(
                        key_file.read(),
                        password=None
                    )
            except FileNotFoundError:
                raise Exception("Missing server_private.pem!")

        # 1. Decode Base64
        enc_payload = base64.b64decode(enc_payload_b64)
        enc_key = base64.b64decode(enc_key_b64)
        
        # 2. Decrypt AES Key (RSA)
        aes_key_bytes = self._private_key.decrypt(
            enc_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # 3. Decrypt Payload (AES-GCM)
        # Expecting IV (12 bytes) + Ciphertext + Tag (16 bytes)
        # But wait, did client send IV? Standard practice: IV is prepended to payload.
        # Let's assume standard GCM packing: [IV(12)][Ciphertext][Tag(16)]
        
        iv = enc_payload[:12]
        tag = enc_payload[-16:]
        ciphertext = enc_payload[12:-16]
        
        decryptor = Cipher(
            algorithms.AES(aes_key_bytes),
            modes.GCM(iv, tag),
        ).decryptor()
        
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext.decode("utf-8")

    async def SendAppList(self, request, context):
        try:
            apps = json.loads(request.apps_json)
            # ... (parsing logic remains same) ...
            
            # [ADAPTIVE] Handle both ["App"] and [{"name":"App", ...}]
            parsed_apps = []
            raw_app_names = []
            
            for item in apps:
                if isinstance(item, str):
                    parsed_apps.append({"name": item, "title": "", "url": "", "is_active": True})
                    raw_app_names.append(item)
                elif isinstance(item, dict):
                    parsed_apps.append(item)
                    raw_app_names.append(item.get("name", ""))

            # ------------------------------------------------------------------
            # 1. Static & Dynamic Blacklist Check (Fast Filter)
            # ------------------------------------------------------------------
            for app_name in raw_app_names:
                app_lower = app_name.lower()
                for bad in self.SERVER_BLACKLIST:
                    if bad.lower() in app_lower:
                        kill_target = app_name
                        command = "KILL"
                        # [AI INTEG] Generate fresh scolding even for known games
                        msg = await self._generate_scolding(app_name)
                        print(f"🚫 [Tracking] SERVER DETECTED BLACKLIST: {app_name}")
                        
                        # [Kafka] Send Scolding Event (Fire & Forget)
                        await kafka_producer.send_event(
                            topic=get_settings().KAFKA_TOPIC_FEEDBACK,
                            event_type="SCOLDING",
                            payload={
                                "target_app": app_name,
                                "message": msg,
                                "emotion": "ANGRY",
                                "source": "STATIC_BLACKLIST"
                            }
                        )
                        break
                if command == "KILL":
                    break
            
            # ------------------------------------------------------------------
            # 2. AI Game Detection (Deep Filter) - Only if safe so far
            # ------------------------------------------------------------------
            if command != "KILL":
                # Find unknown apps (Not in Blacklist AND Not in Whitelist)
                unknown_apps = []
                for name in raw_app_names:
                    # Logic: If partial match with Safe List, consider safe? 
                    # For safety, let's require exact match or strict knowledge for now.
                    # But since process names vary, we check if it's already known safe.
                    if name not in self.KNOWN_SAFE_APPS:
                        unknown_apps.append(name)
                
                if unknown_apps:
                    print(f"🧐 [Tracking] Inspecting Unknown Apps: {unknown_apps}")
                    try:
                        from app.services import game_detector
                        from app.schemas.game import GameDetectRequest
                        
                        detect_res = await game_detector.detect_games(
                            GameDetectRequest(apps=unknown_apps)
                        )
                        
                        if detect_res.is_game_detected:
                            # AI Caught a new game!
                            target = detect_res.target_app or detect_res.detected_games[0]
                            print(f"🤖 [Tracking] AI DETECTED GAME: {target}")
                            
                            # Learning: Add to Blacklist
                            self.SERVER_BLACKLIST.append(target)
                            
                            kill_target = target
                            command = "KILL"
                            msg = detect_res.message
                            
                            # [Kafka] Send Scolding Event
                            await kafka_producer.send_event(
                                topic=get_settings().KAFKA_TOPIC_FEEDBACK,
                                event_type="SCOLDING",
                                payload={
                                    "target_app": target,
                                    "message": msg,
                                    "emotion": "ANGRY",
                                    "source": "AI_GAME_DETECTOR"
                                }
                            )
                        else:
                            # AI said safe: Add to Whitelist
                            # print(f"✅ [Tracking] AI Verified Safe: {unknown_apps}")
                            for safe_app in unknown_apps:
                                self.KNOWN_SAFE_APPS.add(safe_app)

                    except Exception as ai_e:
                        print(f"⚠️ [Tracking] AI Detection Failed: {ai_e}")

            # ------------------------------------------------------------------
            # 3. Passive Logic ...
            # ------------------------------------------------------------------

            # InfluxDB Write API
            from app.core.influx import InfluxClientWrapper
            write_api = InfluxClientWrapper.get_write_api()
            bucket = get_settings().INFLUXDB_BUCKET
            org = get_settings().INFLUXDB_ORG
            
            # Helper to save activity
            from influxdb_client import Point
            
            # Clipboard Logic (4th Data Source)
            # Now using Hybrid Encryption (Payload + Key)
            if request.clipboard_payload:
                 try:
                     # 1. Decrypt
                     decrypted_text = self._decrypt_clipboard(request.clipboard_payload, request.clipboard_key)
                     
                     # 2. AI Analysis (What is this text?)
                     # We use Haiku for fast classification (Code, Error, Chat, Password, etc.)
                     analysis = await self._analyze_clipboard(decrypted_text)
                     
                     # 3. Store Metadata (NOT raw text, for privacy) + Encrypted Blob
                     p_clip = Point("user_clipboard") \
                        .tag("user_id", "dev1") \
                        .tag("content_type", analysis.get("type", "UNKNOWN")) \
                        .field("enc_payload", request.clipboard_payload) \
                        .field("enc_key", request.clipboard_key or "") \
                        .field("summary", analysis.get("summary", "")) \
                        .field("char_count", len(decrypted_text))
                     
                     write_api.write(bucket=bucket, org=org, record=p_clip)
                     # print(f"📋 [Tracking] Clipboard: {analysis.get('summary')}")

                 except Exception as dec_e:
                     print(f"⚠️ [Tracking] Decryption Failed: {dec_e}")
                     # Save raw encrypted only if decryption fails
                     p_clip = Point("user_clipboard") \
                        .tag("user_id", "dev1") \
                        .tag("content_type", "ENCRYPTED_ONLY") \
                        .field("enc_payload", request.clipboard_payload) \
                        .field("enc_key", request.clipboard_key or "") 
                     write_api.write(bucket=bucket, org=org, record=p_clip)

            for app_info in parsed_apps:
                app_name = app_info.get("name", "Unknown")
                title = app_info.get("title", "")
                
                # Check KILL again just in case AI found it
                if kill_target and (app_name == kill_target or app_name in self.SERVER_BLACKLIST):
                     command = "KILL"
                     break

                # 2. Passive Recording (Save 'Active' Window context)
                # Only save if it's the active window to avoid noise
                if app_info.get("is_active", False) and command != "KILL":
                     p = Point("user_activity") \
                        .tag("user_id", "dev1") \
                        .tag("category", "PASSIVE") \
                        .tag("app_name", app_name) \
                        .field("window_title", title) \
                        .field("url", app_info.get("url", "")) \
                        .field("duration_min", 1.0) # Assume 1 min heartbeat
                     
                     write_api.write(bucket=bucket, org=org, record=p)
                     # print(f"👁️ [Tracking] Logged: {app_name} - {title}")
            
            return tracking_pb2.AppListResponse(
                success=True,
                message=msg,
                command=command,
                target_app=kill_target
            )
        except Exception as e:
            print(f"❌ [Tracking] Service Error: {e}")
            return tracking_pb2.AppListResponse(success=False, message=str(e))
