from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
import base64
import os

# Load Private Key
KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "private_key.pem")
try:
    with open(KEY_PATH, "rb") as f:
        PRIVATE_KEY = RSA.import_key(f.read())
except FileNotFoundError:
    print(f"[Crypto] Private key not found at {KEY_PATH}. Decryption will fail.")
    PRIVATE_KEY = None

def decrypt_data_raw(
    encrypted_payload: bytes,
    encrypted_key: bytes,
    iv: bytes,
    tag: bytes
) -> str:
    """
    Decrypts Hybrid Encrypted Data (AES+RSA)
    """
    if not PRIVATE_KEY:
        raise ValueError("Private Key not loaded")

    # 1. Decrypt AES Key using RSA Private Key
    cipher_rsa = PKCS1_OAEP.new(PRIVATE_KEY)
    aes_key = cipher_rsa.decrypt(encrypted_key)

    # 2. Decrypt Payload using AES Key
    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    plaintext = cipher_aes.decrypt_and_verify(encrypted_payload, tag)

    return plaintext.decode('utf-8')
