import os
from functools import lru_cache
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class SecurityService:
    def __init__(self, private_key_path: str = "/app/server_private.pem"):
        self.private_key = self._load_private_key(private_key_path)

    def _load_private_key(self, path: str):
        """Load RSA Private Key from file."""
        if not os.path.exists(path):
            print(f"⚠️ Warning: Private key not found at {path}. Security features disabled.")
            return None
            
        try:
            with open(path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            print(f"✅ Secure Private Key Loaded from {path}")
            return private_key
        except Exception as e:
            print(f"❌ Error loading private key: {e}")
            return None

    def decrypt_session_key(self, encrypted_session_key: bytes) -> bytes:
        """
        Decrypt the AES session key using RSA Private Key.
        Assumes OAEP padding with SHA-256 (Common standard).
        """
        if not self.private_key:
            raise ValueError("Private key not loaded")

        try:
            session_key = self.private_key.decrypt(
                encrypted_session_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return session_key
        except Exception as e:
            raise ValueError(f"Failed to decrypt session key: {e}")

    def decrypt_aes(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """
        Decrypt data using AES-GCM.
        
        Args:
            ciphertext: The encrypted data
            key: AES Key (32 bytes associated with AES-256)
            iv: Initialization Vector (Nonce) - 12 bytes recommended for GCM
        """
        try:
            # Construct Cipher
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # GCM allows passing associated data, but we assume none for now.
            # ciphertext in GCM usually includes the tag at the end.
            # If the client splits tag and ciphertext, we'd need to know.
            # Standard python cryptography library expects the tag passed separately to `finalize_with_tag` 
            # OR appended if using the high-level API?
            # Wait, `modes.GCM` in `primitives.ciphers` handles the authentication tag.
            # But usually libraries (like simple wrappers) might append tag or not.
            # Let's assume the standard: Ciphertext size = Plaintext size. Tag is extra.
            # However, in many stream protocols, Tag is appended. 
            # Let's try the standard approach: Last 16 bytes are the tag if not specified otherwise.
            
            if len(ciphertext) < 16:
                raise ValueError("Ciphertext too short (must include 16-byte tag)")
                
            tag = ciphertext[-16:]
            actual_ciphertext = ciphertext[:-16]
            
            decryptor.authenticate_additional_data(b"") # Optional: AAD
            
            plaintext = decryptor.update(actual_ciphertext) + decryptor.finalize_with_tag(tag)
            return plaintext
            
        except Exception as e:
            print(f"AES Decryption Error: {e}")
            raise ValueError(f"AES Decryption failed: {e}")

@lru_cache()
def get_security_service():
    # Use environment var or default path
    # In K8s, it's at /app/server_private.pem
    # In Local, maybe ./server_private.pem
    path = os.getenv("PRIVATE_KEY_PATH", "server_private.pem")
    if not os.path.exists(path):
        path = "/app/server_private.pem" # Fallback for container
        
    return SecurityService(path)
