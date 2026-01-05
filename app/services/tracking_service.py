import grpc
import json
from app.protos import tracking_pb2, tracking_pb2_grpc

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
