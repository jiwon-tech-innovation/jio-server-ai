import sys
from unittest.mock import MagicMock, AsyncMock, patch

# 1. Mock dependencies GLOBALLY before importing app.services.memory_service
# This prevents the singleton `memory_service = MemoryService()` from triggering real DB connections at import time.
mock_memory_core = MagicMock()
mock_memory_core.get_vector_store.return_value = MagicMock()
mock_memory_core.get_long_term_store.return_value = MagicMock()
sys.modules["app.core.memory"] = mock_memory_core

mock_redis_module = MagicMock()
mock_redis_client = AsyncMock()
mock_redis_module.get_redis_client.return_value = mock_redis_client
sys.modules["app.core.redis_client"] = mock_redis_module

# 2. Now import the service (it will use the mocked modules)
from app.services.memory_service import MemoryService

import unittest

class TestRedisMemory(unittest.IsolatedAsyncioTestCase):
    async def test_sliding_window(self):
        # Setup Redis Mock Behavior
        mock_redis_client.lrange.return_value = [
            '{"role": "User", "content": "Hi", "timestamp": "t1"}',
            '{"role": "AI", "content": "Hello", "timestamp": "t2"}'
        ]
        
        # Instantiate (or use the one created at import, which used mocks)
        service = MemoryService()
        
        # Ensure the service is using our mock clietn
        service.redis = mock_redis_client
            
        # 1. Test Add Log
        await service.add_chat_log("test_user", "User", "New Message")
        
        # Verify Push and Trim
        mock_redis_client.rpush.assert_called_once()
        mock_redis_client.ltrim.assert_called_once_with("chat_history:test_user", -20, -1)
        
        # 2. Test Get Recent
        history = await service.get_recent_chat("test_user", k=2)
        
        # Verify Format
        self.assertIn("User: Hi", history)
        self.assertIn("AI: Hello", history)
        print(f"Retrieved History:\n{history}")

if __name__ == "__main__":
    unittest.main()
