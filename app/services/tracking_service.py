import grpc
import json
import traceback
from app.protos import tracking_pb2, tracking_pb2_grpc
from app.core.security import get_security_service

class TrackingService(tracking_pb2_grpc.TrackingServiceServicer):
    def __init__(self):
        self.security_service = get_security_service()

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
            
            return tracking_pb2.AppListResponse(
                success=True,
                message=msg,
                command=command,
                target_app=kill_target
            )
        except Exception as e:
            print(f"❌ [Tracking] Service Error: {e}")
            return tracking_pb2.AppListResponse(success=False, message=str(e))

    async def SendClipboard(self, request, context):
        """
        Receives simple AES-encrypted clipboard text.
        Decrypts it using RSA-decrypted valid session key.
        """
        try:
            encrypted_content = request.encrypted_content
            encrypted_session_key = request.session_key
            iv = request.iv
            
            # 1. Decrypt Session Key
            aes_key = self.security_service.decrypt_session_key(encrypted_session_key)
            
            # 2. Decrypt Content
            plaintext_bytes = self.security_service.decrypt_aes(encrypted_content, aes_key, iv)
            clipboard_text = plaintext_bytes.decode('utf-8')
            
            print(f"📋 [Clipboard] Decrypted: {clipboard_text}")
            
            # TODO: Store or Analyze clipboard_text
            
            return tracking_pb2.ClipboardResponse(
                success=True,
                message="Clipboard Received & Decrypted"
            )
        except Exception as e:
            print(f"❌ [Clipboard] Decryption Error: {e}")
            traceback.print_exc()
            return tracking_pb2.ClipboardResponse(
                success=False,
                message=f"Decryption Failed: {str(e)}"
            )
