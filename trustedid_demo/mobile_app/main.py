from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from mobile_app.crypto_engine import TEE
import requests

app = FastAPI()
templates = Jinja2Templates(directory="mobile_app/templates")

IDP_URL = "http://127.0.0.1:8000"
BANK_URL = "http://127.0.0.1:8001"

@app.get("/")
async def index(request: Request):
    res = requests.get(f"{BANK_URL}/request-login").json()
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "rp_nonce": res['rp_nonce'],
    })


@app.post("/check-account")
async def check_account(account_ref: str = Form(...)):
    try:
        response = requests.post(
            f"{BANK_URL}/check-account",
            json={"account_ref": account_ref},
            timeout=10,
        )
    except requests.RequestException:
        return {"exists": False, "detail": "Không thể kết nối tới hệ thống kiểm tra tài khoản."}

    if response.status_code != 200:
        detail = response.json().get("detail", "Tài khoản không hợp lệ.")
        return {"exists": False, "detail": detail}

    payload = response.json()
    return {
        "exists": True,
        "uid": payload["uid"],
        "account_number": payload["account_number"],
        "status": payload["status"],
    }

@app.post("/do-auth")
async def do_auth(request: Request, username: str = Form(...), pin: str = Form(...), rp_nonce: str = Form(...)):
    u_nonce = TEE.generate_u_nonce()
    pin_hash = TEE.hash_pin(pin)

    idp_res = requests.post(f"{IDP_URL}/authorize", json={
        "username": username,
        "pin_hash": pin_hash,
        "u_nonce": u_nonce,
        "rp_challenge": rp_nonce
    }).json()
    
    if "id_token" not in idp_res:
        return {"error": "Xác thực IdP thất bại, vui lòng kiểm tra Terminal."}
        
    # Gửi Token về Bank để đối soát và lấy dữ liệu SQL thật
    bank_res = requests.post(f"{BANK_URL}/verify", json={
        "id_token": idp_res['id_token'],
        "u_nonce": u_nonce,
        "rp_nonce": rp_nonce
    }).json()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "result": bank_res
    })

@app.post("/do-transfer")
async def do_transfer(account_number: str = Form(...), amount: int = Form(...), beneficiary: str = Form(...)):
    """Gọi API trừ tiền thật của ngân hàng khi hoàn tất Step-up LoA4"""
    res = requests.post(f"{BANK_URL}/transfer", json={
        "account_number": account_number,
        "amount": amount,
        "beneficiary": beneficiary,
        "description": "Xác thực ngoài băng LoA4"
    }).json()
    return res