from __future__ import annotations

import argparse
from io import BytesIO
import sys
from pathlib import Path

from twisted.internet import reactor
from twisted.internet import protocol
from twisted.python import components, log
from ldaptor import inmemory
from ldaptor import interfaces
from ldaptor.protocols.ldap import ldapserver


class LDAPServerFactory(protocol.ServerFactory):
    def __init__(self, root):
        self.root = root


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local LDAP server backed by an LDIF file.")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind to.")
    parser.add_argument("--port", type=int, default=10389, help="TCP port to listen on.")
    parser.add_argument(
        "--ldif",
        default=Path(__file__).resolve().parent / "bootstrap" / "50-bootstrap.ldif",
        type=Path,
        help="LDIF file used to seed the LDAP tree.",
    )
    return parser


def start_server(db, host: str, port: int):
    factory = LDAPServerFactory(db)
    factory.protocol = ldapserver.LDAPServer
    components.registerAdapter(
        lambda x: x.root,
        LDAPServerFactory,
        interfaces.IConnectedLDAPEntry,
    )
    reactor.listenTCP(port, factory, interface=host)
    print(f"LDAP server listening on ldap://{host}:{port}")


def main() -> int:
    args = build_argument_parser().parse_args()

    if not args.ldif.exists():
        print(f"LDIF file not found: {args.ldif}", file=sys.stderr)
        return 1

    log.startLogging(sys.stderr)

    ldif_bytes = args.ldif.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    deferred = inmemory.fromLDIFFile(BytesIO(ldif_bytes))

    deferred.addCallback(start_server, args.host, args.port)
    deferred.addErrback(log.err)
    reactor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())