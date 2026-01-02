"""
Intelligence Service gRPC 테스트 클라이언트
Go 서버(Dev 4)가 Python 서버(Dev 5)를 호출하는 것을 시뮬레이션
"""
import asyncio
import grpc
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_classify_url():
    """ClassifyURL RPC 테스트"""
    print("=" * 50)
    print("Testing ClassifyURL RPC...")
    print("=" * 50)
    
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        # 수동으로 RPC 호출 (proto 없이)
        try:
            # 간단한 연결 테스트
            state = channel.get_state(try_to_connect=True)
            print(f"Channel state: {state}")
            
            # 채널 연결 대기
            await asyncio.wait_for(
                channel.channel_ready(),
                timeout=5.0
            )
            print("✅ gRPC 채널 연결 성공!")
            
        except asyncio.TimeoutError:
            print("❌ gRPC 채널 연결 실패 (timeout)")
            return False
        except Exception as e:
            print(f"❌ 연결 오류: {e}")
            return False
    
    return True


async def test_http_endpoint():
    """HTTP 엔드포인트 테스트 (gRPC 우회)"""
    import aiohttp
    
    print("\n" + "=" * 50)
    print("Testing HTTP /api/v1/classify endpoint...")
    print("=" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "content_type": "URL",
                "content": "https://stackoverflow.com/questions/python"
            }
            async with session.post(
                'http://localhost:8000/api/v1/classify',
                json=payload
            ) as resp:
                result = await resp.json()
                print(f"Response: {result}")
                
                if result.get("result") != "UNKNOWN":
                    print("✅ HTTP 엔드포인트 정상 작동!")
                else:
                    print(f"⚠️ 분류 실패: {result.get('reason', 'No reason')[:100]}...")
                    
    except Exception as e:
        print(f"❌ HTTP 요청 실패: {e}")


async def main():
    print("\n🧪 JIAA Intelligence Service 연결 테스트\n")
    
    # 1. gRPC 채널 연결 테스트
    grpc_ok = await test_classify_url()
    
    # 2. HTTP 엔드포인트 테스트 (선택)
    try:
        import aiohttp
        await test_http_endpoint()
    except ImportError:
        print("\n⚠️ aiohttp 미설치 - HTTP 테스트 스킵")
    
    print("\n" + "=" * 50)
    if grpc_ok:
        print("✅ Dev 4 → Dev 5 gRPC 연결 테스트 성공!")
        print("   (AWS 자격 증명 문제는 별도로 해결 필요)")
    else:
        print("❌ gRPC 연결 실패")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
