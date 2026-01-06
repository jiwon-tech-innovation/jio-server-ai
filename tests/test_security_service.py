import unittest
import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from app.core.security import SecurityService

# Mock Private Key Path
TEST_KEY_PATH = "test_private.pem"

class TestSecurityService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Generate a temporary RSA keypair for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        cls.public_key = private_key.public_key()
        
        # Save Private Key to file for SecurityService to load
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(TEST_KEY_PATH, "wb") as f:
            f.write(pem)

    @classmethod
    def tearDownClass(cls):
        # Cleanup
        if os.path.exists(TEST_KEY_PATH):
            os.remove(TEST_KEY_PATH)

    def test_security_flow(self):
        """Test full flow: Encrypt (Client logic) -> Decrypt (Server logic)"""
        # 1. Initialize Service
        service = SecurityService(private_key_path=TEST_KEY_PATH)
        self.assertIsNotNone(service.private_key)
        
        # 2. Simulate Client: Generate Session Key (AES-256)
        aes_key = os.urandom(32)
        iv = os.urandom(12) # GCM Nonce
        
        # 3. Simulate Client: Encrypt Session Key with RSA Public Key
        encrypted_session_key = self.public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # 4. Simulate Client: Encrypt Data with AES-GCM
        data = b"Hello, JIAA Security World!"
        encryptor = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(iv),
            backend=default_backend()
        ).encryptor()
        
        ciphertext = encryptor.update(data) + encryptor.finalize()
        tag = encryptor.tag
        
        # Standard GCM: usually concat ciphertext + tag
        full_encrypted_payload = ciphertext + tag
        
        # 5. Server Logic: Decrypt Session Key
        decrypted_aes_key = service.decrypt_session_key(encrypted_session_key)
        self.assertEqual(decrypted_aes_key, aes_key)
        
        # 6. Server Logic: Decrypt Data
        decrypted_data = service.decrypt_aes(full_encrypted_payload, decrypted_aes_key, iv)
        self.assertEqual(decrypted_data, data)
        print(f"Decrypted Data: {decrypted_data}")

if __name__ == "__main__":
    unittest.main()
