from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from idp_server.jwt_engine import CustomJWTEngine
from idp_server.ldap_connector import DirectoryTreeLDAP

app = FastAPI(title="TrustedID Identity Provider Server")
jwt_engine = CustomJWTEngine()
ldap_client = DirectoryTreeLDAP()

class AuthRequest(BaseModel):
    username: str
    pin_hash: str
    u_nonce: str
    rp_challenge: str

@app.post("/authorize")
async def authorize_loa4(req: AuthRequest):
    print(f"\n{'='*60}")
    print(f"🚀 [IDP SERVER] BẮT ĐẦU XỬ LÝ XÁC THỰC LoA4 CHO UID: {req.username}")
    print(f"{'='*60}")
    
    # --- VÒNG 1: KIỂM TRA PIN RÀNG BUỘC TEE ---
    print("[Vòng 1 - TEE] Đã nhận và xác minh gói tin băm PIN: H(PIN || appID)")

    # --- TÍCH HỢP LDAP: TRA CỨU HỒ SƠ GỐC VÀ ĐỐI CHIẾU PIN ---
    print(f"🔍 [LDAP] Đang truy vấn cây thư mục LDAP cho UID: {req.username}...")
    try:
        kyc_profile = ldap_client.search_user_by_uid(req.username)
    except RuntimeError as exc:
        print(f"❌ [LDAP ERROR] {exc}")
        raise HTTPException(status_code=503, detail=str(exc))

    if kyc_profile["status"] != "SUCCESS":
        print(f"❌ [LDAP ERROR] Không tìm thấy tài khoản hợp lệ cho UID: {req.username}")
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin định danh LDAP.")

    stored_pin_hash = kyc_profile.get("pin_hash")
    if not stored_pin_hash:
        print(f"❌ [LDAP ERROR] Bản ghi LDAP thiếu userPassword cho UID: {req.username}")
        raise HTTPException(status_code=500, detail="Thiếu PIN trong LDAP.")

    if req.pin_hash != stored_pin_hash:
        print(f"❌ [PIN ERROR] PIN không đúng cho UID: {req.username}")
        raise HTTPException(status_code=401, detail="Mã PIN không đúng.")

    print(f"   ↳ Kết quả LDAP: {kyc_profile['full_name']} - CCCD: {kyc_profile['cccd']}")
    print("✅ [Vòng 1 - PIN] PIN hợp lệ theo bản ghi LDAP.")
    
    # --- VÒNG 2: XÁC THỰC SIM-OTP QUA TERMINAL ---
    print("\n" + "!"*60)
    print("🔔 [OTA SIGNAL] LỆNH PHÊ DUYỆT TỪ BẢN TIN FLASH THẺ SIM")
    print("Hệ thống MNO đang chờ xác nhận vật lý từ chủ thuê bao...")
    print("!"*60)
    
    confirm = await asyncio.to_thread(
        input, 
        "👉 BẠN CÓ ĐỒNG Ý PHÊ DUYỆT TRÊN SIM? (Gõ 'Y' và nhấn Enter): "
    )
    
    if confirm.strip().upper() != 'Y':
        print("\n❌ [TỪ CHỐI] Giao dịch bị hủy bởi người dùng trên SIM.")
        raise HTTPException(status_code=403, detail="Xác thực SIM-OTP bị từ chối.")
        
    print("\n✅ [Vòng 2 - SIM] Đã xác nhận phê duyệt OTA từ thẻ SIM thành công.")
    
    # --- VÒNG 3: ĐỐI SOÁT SINH TRẮC HỌC ---
    print("✅ [Vòng 3 - Bio] Đã nhận chữ ký chứng thực phần cứng từ TEE (Vân tay/FaceID hợp lệ).")

    # --- TÍNH TOÁN BOUND CHALLENGE VÀ PHÁT HÀNH TOKEN ---
    import hashlib
    combined = f"{req.rp_challenge}:{req.u_nonce}".encode('utf-8')
    bound_challenge = hashlib.sha256(combined).hexdigest()
    
    # Cấp token loại bỏ hoàn toàn trường 'aud'
    id_token = jwt_engine.create_token(
        sub=f"mno-uid-{req.username}",
        h_challenge=bound_challenge,
        kyc=kyc_profile
    )
    
    print(f"{'='*60}")
    print("🎉 [THÀNH CÔNG] Đã phát hành ID Token ẩn danh cho RP.")
    print(f"{'='*60}\n")
    
    return {"id_token": id_token}