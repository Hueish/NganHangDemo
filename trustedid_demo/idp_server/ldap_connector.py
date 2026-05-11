"""Kết nối LDAP thật bằng ldap3.

Connector này đọc cấu hình từ biến môi trường để truy vấn LDAP server thật
thay vì dùng file JSON giả lập.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPExceptionError


@dataclass(frozen=True)
class LDAPConfig:
    server_uri: str
    base_dn: str
    bind_dn: str | None = None
    bind_password: str | None = None
    start_tls: bool = False


class DirectoryTreeLDAP:
    def __init__(self):
        self.config = LDAPConfig(
            server_uri=os.getenv("LDAP_SERVER_URI", "ldap://localhost:10389").strip(),
            base_dn=os.getenv("LDAP_BASE_DN", "ou=users,dc=ptitbank,dc=local").strip(),
            bind_dn=os.getenv("LDAP_BIND_DN", "").strip() or None,
            bind_password=os.getenv("LDAP_BIND_PASSWORD", "").strip() or None,
            start_tls=os.getenv("LDAP_STARTTLS", "false").strip().lower() in {"1", "true", "yes", "on"},
        )

    def _build_server(self) -> Server:
        if not self.config.server_uri:
            raise RuntimeError("LDAP_SERVER_URI chưa được cấu hình.")

        parsed = urlparse(self.config.server_uri)
        scheme = parsed.scheme.lower()
        host = parsed.hostname or self.config.server_uri
        port = parsed.port
        use_ssl = scheme == "ldaps"

        if scheme not in {"ldap", "ldaps", ""}:
            raise RuntimeError(f"LDAP_SERVER_URI không hợp lệ: {self.config.server_uri}")

        return Server(host, port=port, use_ssl=use_ssl, get_info=ALL)

    def _connect(self) -> Connection:
        server = self._build_server()

        try:
            connection = Connection(
                server,
                user=self.config.bind_dn,
                password=self.config.bind_password,
                auto_bind=False,
                raise_exceptions=True,
            )

            if self.config.start_tls:
                connection.start_tls()

            connection.bind()
            return connection
        except LDAPExceptionError as exc:
            raise RuntimeError(f"Không thể kết nối/bind LDAP: {exc}") from exc

    @staticmethod
    def _first_value(attributes: dict, *names: str):
        for name in names:
            value = attributes.get(name)
            if isinstance(value, list):
                if value:
                    return value[0]
            elif value not in (None, ""):
                return value
        return None

    def add_user(self, uid: str, profile: dict):
        if not self.config.base_dn:
            raise RuntimeError("LDAP_BASE_DN chưa được cấu hình.")

        dn = f"uid={uid},{self.config.base_dn}"
        attributes = {
            "objectClass": ["top", "person", "organizationalPerson", "inetOrgPerson"],
            "uid": uid,
            "cn": profile.get("cn") or profile.get("full_name") or uid,
            "sn": profile.get("sn") or profile.get("full_name") or uid,
            "mail": profile.get("mail") or profile.get("email") or "",
            "telephoneNumber": profile.get("telephoneNumber") or profile.get("mobile") or profile.get("phone") or "",
            "mobile": profile.get("mobile") or profile.get("phone") or "",
            "description": profile.get("description") or profile.get("idCardNumber") or profile.get("cccd") or "",
            "employeeNumber": profile.get("employeeNumber") or profile.get("accountNumber") or profile.get("account_number") or "",
            "userPassword": profile.get("userPassword") or profile.get("pin_hash") or "",
        }

        try:
            with self._connect() as connection:
                connection.add(dn, attributes=attributes)
                if connection.result.get("description") != "success":
                    raise RuntimeError(connection.result.get("message") or "LDAP add failed.")
        except LDAPExceptionError as exc:
            raise RuntimeError(f"Không thể thêm bản ghi LDAP: {exc}") from exc

        return {"status": "SUCCESS", "dn": dn}

    def user_exists(self, uid_input: str):
        return self.search_user_by_uid(uid_input)["status"] == "SUCCESS"

    def search_user_by_uid(self, uid_input: str):
        """Tìm bản ghi LDAP thật theo uid."""
        if not self.config.base_dn:
            raise RuntimeError("LDAP_BASE_DN chưa được cấu hình.")

        search_filter = f"(&(objectClass=inetOrgPerson)(uid={uid_input}))"
        attributes = [
            "cn",
            "mail",
            "mobile",
            "telephoneNumber",
            "description",
            "employeeNumber",
            "userPassword",
            "uid",
        ]

        try:
            with self._connect() as connection:
                connection.search(
                    search_base=self.config.base_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes,
                )

                if not connection.entries:
                    return {"status": "ENTRY_NOT_FOUND"}

                entry = connection.entries[0]
                entry_attributes = entry.entry_attributes_as_dict
                return {
                    "status": "SUCCESS",
                    "dn": entry.entry_dn,
                    "full_name": self._first_value(entry_attributes, "cn") or uid_input,
                    "email": self._first_value(entry_attributes, "mail"),
                    "phone": self._first_value(entry_attributes, "mobile", "telephoneNumber"),
                    "cccd": self._first_value(entry_attributes, "description"),
                    "account_number": self._first_value(entry_attributes, "employeeNumber"),
                    "pin_hash": self._first_value(entry_attributes, "userPassword"),
                }
        except LDAPExceptionError as exc:
            raise RuntimeError(f"Không thể truy vấn LDAP: {exc}") from exc