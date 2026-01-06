import unittest
import os
import json
from unittest.mock import MagicMock, AsyncMock
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from app.services.tracking_service import TrackingService

# Mock Private Key for Service
TEST_KEY_PATH = "test_clipboard_private.pem"

class TestTrackingSecurity(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Generate Keypair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        cls.public_key = private_key.public_key()
        
        # 2. Save Private Key
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(TEST_KEY_PATH, "wb") as f:
            f.write(pem)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_KEY_PATH):
            os.remove(TEST_KEY_PATH)

    async def test_send_clipboard_decryption(self):
        # Setup Service (inject mock key path via env or mocking SecurityService?)
        # Since TrackingService uses `get_security_service` which loads from ENV or File.
        # We'll set ENV for the test.
        os.environ["PRIVATE_KEY_PATH"] = TEST_KEY_PATH
        
        service = TrackingService()
        
        # Prepare Encrypted Payload
        clipboard_content = "Secret Clipboard Content 1234"
        aes_key = os.urandom(32)
        iv = os.urandom(12)
        
        # Encrypt Content (Client logic)
        encryptor = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(iv),
            backend=default_backend()
        ).encryptor()
        
        ciphertext = encryptor.update(clipboard_content.encode()) + encryptor.finalize()
        tag = encryptor.tag
        encrypted_content = ciphertext + tag
        
        # Encrypt Session Key (Client logic)
        encrypted_session_key = self.public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Mock Request
        mock_request = MagicMock()
        mock_request.encrypted_content = encrypted_content
        mock_request.session_key = encrypted_session_key
        mock_request.iv = iv
        
        mock_context = MagicMock()
        
        # Call Service
        response = await service.SendClipboard(mock_request, mock_context)
        
        # Verify
        self.assertTrue(response.success)
        self.assertIn("Decrypted", response.message)

if __name__ == "__main__":
    unittest.main()
