import jwt, time
from cryptography.hazmat.primitives import serialization

class CustomJWTEngine:
    def __init__(self):
        with open("keys/idp_private.pem", "rb") as f:
            self.key = serialization.load_pem_private_key(f.read(), password=None)

    def create_token(self, sub, h_challenge, kyc):
        payload = {
            "iss": "https://trustedid.idp.vn",
            "sub": sub,
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "auth_assurance": {"level": "LoA4", "factors": ["pin", "sim", "bio"]},
            "bound_challenge": h_challenge, # Thay cho 'aud' để bảo vệ quyền riêng tư
            "kyc": kyc
        }
        return jwt.encode(payload, self.key, algorithm="RS256")