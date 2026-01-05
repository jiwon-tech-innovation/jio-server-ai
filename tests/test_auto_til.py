import asyncio
import sys
import unittest
import os
import shutil
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.append(".")

# Mock Config
with patch("app.core.config.get_settings") as mock_settings:
    mock_settings.return_value.PROJECT_NAME = "Test"
    mock_settings.return_value.BEDROCK_REGION = "us-east-1"
    
    from app.services.review_service import review_service
    from app.api.v1.endpoints.review import create_auto_blog, BlogRequest

class TestAutoBlog(unittest.TestCase):
    
    def setUp(self):
        # Create a temp directory for desktop simulation
        self.test_dir = os.path.join(os.getcwd(), "test_desktop")
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
            
    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    async def test_endpoint_logic(self):
        # Mocking the generate_blog_post method
        with patch("app.services.review_service.review_service.generate_blog_post", new_callable=AsyncMock) as mock_method:
            mock_method.return_value = {
                "status": "SAVED", 
                "filename": "Blog_Test.md", 
                "file_path": "/tmp/Blog_Test.md"
            }
            
            # Case 1: Full Input
            request = BlogRequest(
                error_log="NullPointer", 
                solution_code="print('fixed')", 
                user_id="dev1"
            )
            response = await create_auto_blog(request)
            self.assertEqual(response.status, "SAVED")
            mock_method.assert_called()

            # Case 2: No Error Log (Daily Summary Only)
            request2 = BlogRequest(user_id="dev1")
            response2 = await create_auto_blog(request2)
            self.assertEqual(response2.status, "SAVED")
            
    def test_run_async(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.test_endpoint_logic())
        loop.close()

if __name__ == "__main__":
    unittest.main()
