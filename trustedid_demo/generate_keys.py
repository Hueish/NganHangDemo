import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_key(name):
    os.makedirs("keys", exist_ok=True)
    priv_path = f"keys/{name}_private.pem"
    pub_path = f"keys/{name}_public.pem"
    
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(pub_path, "wb") as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    print(f"✅ Đã tạo khóa cho {name}")

if __name__ == "__main__":
    generate_key("idp")
    generate_key("tee") # Khóa giả lập cho vùng an toàn thiết bị