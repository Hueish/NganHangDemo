# init_sql_db.py
import os
import re
import sqlite3
from pathlib import Path


LDAP_LDIF_PATH = Path("ldap/bootstrap/50-bootstrap.ldif")


def load_ldap_users_from_ldif():
    """Extract uid, cn, and employeeNumber from the LDAP bootstrap LDIF."""
    if not LDAP_LDIF_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy LDIF LDAP: {LDAP_LDIF_PATH}")

    users = []
    current = {}
    entry_lines = []

    def flush_entry():
        nonlocal current, entry_lines
        if not entry_lines:
            return

        entry_text = "\n".join(entry_lines).strip()
        dn_match = re.search(r"^dn:\s*(.+)$", entry_text, re.MULTILINE)
        uid_match = re.search(r"^uid:\s*(.+)$", entry_text, re.MULTILINE)
        cn_match = re.search(r"^cn:\s*(.+)$", entry_text, re.MULTILINE)
        employee_number_match = re.search(r"^employeeNumber:\s*(.+)$", entry_text, re.MULTILINE)

        if dn_match and uid_match and employee_number_match:
            uid = uid_match.group(1).strip()
            cn = cn_match.group(1).strip() if cn_match else uid
            account_number = employee_number_match.group(1).strip()
            users.append({"uid": uid, "cn": cn, "account_number": account_number})

        current = {}
        entry_lines = []

    with LDAP_LDIF_PATH.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if not line:
                flush_entry()
                continue
            entry_lines.append(line)

    flush_entry()
    return users

def initialize_sql_database():
    db_path = "ptitbank_core.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. TẠO BẢNG TÀI KHOẢN (Chỉ chứa số dư và trạng thái, không chứa KYC)
    cursor.execute("""
    CREATE TABLE accounts (
        account_number TEXT PRIMARY KEY,
        uid TEXT NOT NULL,
        balance INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    """)
    
    # 2. TẠO BẢNG LỊCH SỬ GIAO DỊCH
    cursor.execute("""
    CREATE TABLE transactions (
        tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_number TEXT NOT NULL,
        type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        description TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_number) REFERENCES accounts(account_number)
    )
    """)
    
    # 3. CHÈN DỮ LIỆU SỐ DƯ CHO 10 NGƯỜI DÙNG LẤY TRỰC TIẾP TỪ LDAP LDIF
    ldap_users = load_ldap_users_from_ldif()
    balance_map = {
        "b23dcat336": 1250000000,
        "b23dcat101": 500000000,
        "trang_ninh": 5000000000,
        "leminh_anh": 120000000,
        "pham_quang_huy": 890000000,
        "nguyen_thao_vy": 340000000,
        "do_hoang_long": 670000000,
        "vu_minh_tuan": 230000000,
        "hoai_anh": 450000000,
        "phuc_dat": 750000000,
    }
    status_map = {
        "trang_ninh": "VIP_ACTIVE",
    }

    users_data = []
    for user in ldap_users:
        uid = user["uid"]
        users_data.append((
            user["account_number"],
            uid,
            balance_map.get(uid, 100000000),
            status_map.get(uid, "ACTIVE"),
        ))

    cursor.executemany("INSERT INTO accounts VALUES (?, ?, ?, ?)", users_data)
    
    # 4. CHÈN MỘT SỐ GIAO DỊCH MẪU BAN ĐẦU
    initial_txs = [
        ("888833602026", "CREDIT", 15000000, "Học bổng kỳ 2 - 2026"),
        ("888833602026", "DEBIT", 50000, "Thanh toán Cantine PTIT"),
        ("888810102026", "CREDIT", 5000000, "Nhận tiền từ gia đình"),
        ("999988880000", "CREDIT", 50000000, "Thanh toán phụ cấp đề tài nghiên cứu"),
        ("888811112024", "CREDIT", 2000000, "Hoàn tiền giao dịch"),
        ("888822223025", "DEBIT", 350000, "Thanh toán dịch vụ"),
    ]
    cursor.executemany("INSERT INTO transactions (account_number, type, amount, description) VALUES (?, ?, ?, ?)", initial_txs)
    
    conn.commit()
    conn.close()
    print("✔ Đã khởi tạo thành công CSDL SQL (ptitbank_core.db) cho 10 người dùng!")

if __name__ == "__main__":
    initialize_sql_database()