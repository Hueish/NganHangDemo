from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid, hashlib, jwt, sqlite3

app = FastAPI(title="PTITBank Core Backend")

bank_sessions = {}

class VerifyRequest(BaseModel):
    id_token: str
    u_nonce: str
    rp_nonce: str

class TransferRequest(BaseModel):
    account_number: str
    amount: int
    beneficiary: str
    description: str


class AccountLookupRequest(BaseModel):
    account_ref: str

def get_db_connection():
    conn = sqlite3.connect("ptitbank_core.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.post("/check-account")
async def check_account(data: AccountLookupRequest):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT account_number, uid, balance, status FROM accounts WHERE uid = ? OR account_number = ?",
            (data.account_ref, data.account_ref),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Tài khoản không tồn tại trong CSDL.")

        return {
            "exists": True,
            "uid": row["uid"],
            "account_number": row["account_number"],
            "status": row["status"],
        }
    finally:
        conn.close()

@app.get("/request-login")
def request_login():
    nonce = uuid.uuid4().hex
    bank_sessions[nonce] = True
    return {
        "rp_nonce": nonce,
        "client_id": "ptitbank_mobile_app"
    }

@app.post("/verify")
async def verify(data: VerifyRequest):
    # 1. Bank tự tính toán lại h_challenge để đối soát
    combined = f"{data.rp_nonce}:{data.u_nonce}".encode('utf-8')
    expected_h = hashlib.sha256(combined).hexdigest()
    
    with open("keys/idp_public.pem", "rb") as f:
        pub_key = f.read()
    
    try:
        payload = jwt.decode(data.id_token, pub_key, algorithms=["RS256"])
        
        if payload.get('bound_challenge') != expected_h:
            raise HTTPException(status_code=403, detail="Thử thách ngẫu nhiên không khớp!")
            
        kyc = payload['kyc']
        account_number = kyc['account_number']
        
        # 2. KẾT NỐI SQL LẤY SỐ DƯ VÀ GIAO DỊCH THẬT
        conn = get_db_connection()
        acc_row = conn.execute("SELECT balance, status FROM accounts WHERE account_number = ?", (account_number,)).fetchone()
        
        if not acc_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Tài khoản không tồn tại trong hệ thống Core Banking.")
            
        balance = acc_row['balance']
        
        tx_rows = conn.execute("SELECT type, amount, description, timestamp FROM transactions WHERE account_number = ? ORDER BY tx_id DESC LIMIT 10", (account_number,)).fetchall()
        transactions = [dict(tx) for tx in tx_rows]
        conn.close()
        
        return {
            "status": "Thành công",
            "user": kyc['full_name'],
            "account_number": account_number,
            "balance": balance,
            "cccd": kyc['cccd'],
            "transactions": transactions
        }
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Token không hợp lệ: {str(e)}")

@app.post("/transfer")
async def process_transfer(req: TransferRequest):
    """Xử lý trừ tiền và lưu vết giao dịch vào SQL khi hoàn tất Step-up LoA4"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Kiểm tra số dư hiện tại
        acc = cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (req.account_number,)).fetchone()
        if not acc or acc['balance'] < req.amount:
            raise HTTPException(status_code=400, detail="Số dư không đủ để thực hiện giao dịch.")
            
        # Trừ tiền tài khoản nguồn
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number = ?", (req.amount, req.account_number))
        
        # Ghi nhận lịch sử giao dịch
        cursor.execute("INSERT INTO transactions (account_number, type, amount, description) VALUES (?, ?, ?, ?)",
                       (req.account_number, "DEBIT", req.amount, f"Chuyển tiền cho {req.beneficiary} - {req.description}"))
        
        conn.commit()
        
        # Lấy số dư mới cập nhật
        new_balance = cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (req.account_number,)).fetchone()['balance']
        conn.close()
        
        return {"status": "SUCCESS", "new_balance": new_balance}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý giao dịch: {str(e)}")