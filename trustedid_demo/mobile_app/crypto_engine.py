import hashlib, uuid

class TEE:
    @staticmethod
    def get_app_id(): return "TRUSTED_DEVICE_B23DCAT336"
    
    @staticmethod
    def hash_pin(pin):
        # H(PIN || appID)
        content = f"{pin}:{TEE.get_app_id()}".encode()
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def generate_u_nonce(): return uuid.uuid4().hex