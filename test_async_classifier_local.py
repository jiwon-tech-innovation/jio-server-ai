import asyncio
from app.services.classifier import classify_content
from app.schemas.intelligence import ClassifyRequest

if __name__ == "__main__":
    import time
    
    async def measure(name, coro):
        start = time.time()
        res = await coro
        elapsed = time.time() - start
        print(f"\n[{name}] Result: {res.result} (Conf: {res.confidence})")
        print(f"Reason: {res.reason}")
        print(f"⏱️ Time Taken: {elapsed:.4f}s")

    async def main_test():
        print("🚀 Testing Async Classifier with Fast Path...")

        # Test 1: Code Mode (Fast Path -> STUDY)
        req_code = ClassifyRequest(
            process_info={"process_name": "Code.exe", "window_title": "app.py"},
            content_type="WINDOW"
        )
        await measure("Test 1: Code.exe (Fast Path)", classify_content(req_code))

        # Test 2: URL Mode (Fast Path -> PLAY)
        req_play = ClassifyRequest(
            content_type="URL",
            content="https://www.netflix.com/browse"
        )
        await measure("Test 2: Netflix (Fast Path)", classify_content(req_play))

        # Test 3: Unknown URL (Slow Path -> LLM) -> Often classified as PLAY/STUDY depending on content
        # Using a generic news site or search engine not in the fast list
        req_slow = ClassifyRequest(
            content_type="URL",
            content="https://www.naver.com"
        )
        await measure("Test 3: Naver (Slow Path)", classify_content(req_slow))

        # Test 4: Unknown Game (Search Fallback)
        # "Hollow Knight" is not in fast list, and LLM might not know "hollow_knight.exe" instantly without help?
        # A simple process name "hollow_knight.exe" might be obscure enough to trigger search if confidence is low.
        print("\n[Test 4] Unknown Game (Hollow Knight)... Expecting Search...")
        req_unknown = ClassifyRequest(
            process_info={"process_name": "hollow_knight.exe", "window_title": "Hollow Knight"},
            content_type="WINDOW"
        )
        await measure("Test 4: Hollow Knight (Search)", classify_content(req_unknown))

    asyncio.run(main_test())

