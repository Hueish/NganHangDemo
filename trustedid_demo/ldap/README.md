# Local LDAP

This workspace includes a real local LDAP server implemented with `ldaptor`.

## Start

1. Install dependencies from `requirements.txt`.
2. Run `python ldap/local_ldap_server.py` from the workspace root.
3. Keep the app pointed at `ldap://localhost:10389`.

## Seed data

The bootstrap LDIF loads 10 users under `ou=users,dc=ptitbank,dc=local`.

Fields included:

- `uid`
- `cn`
- `sn`
- `mail`
- `telephoneNumber`
- `mobile`
- `description` for CCCD
- `employeeNumber` for account number

## Demo PINs

Use these PINs in the login screen:

- `b23dcat336` -> `336123`
- `b23dcat101` -> `101234`
- `trang_ninh` -> `903345`
- `leminh_anh` -> `904456`
- `pham_quang_huy` -> `905567`
- `nguyen_thao_vy` -> `906678`
- `do_hoang_long` -> `907789`
- `vu_minh_tuan` -> `908890`
- `hoai_anh` -> `909901`
- `phuc_dat` -> `910012`

## Notes

- The server is read-only and serves the LDIF tree directly.
- If you change the LDIF, restart the server to reload the data.
- A Docker Compose fallback is still present, but the Python server is the working local setup in this workspace.
