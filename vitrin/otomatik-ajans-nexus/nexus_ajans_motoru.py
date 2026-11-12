#!/usr/bin/env python3
"""Local-only agency brief, quote, revision, payment-check and delivery demo."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE / "data" / "nexus-demo.sqlite3"
PACKAGES = {
    "starter": {"name": "Temel vitrin paketi", "price": 12000, "includes": ["Tek sayfalık web vitrini", "İletişim ve teklif formu"]},
    "growth": {"name": "Büyüme paketi", "price": 24000, "includes": ["Çok bölümlü web vitrini", "İçerik ve dönüşüm akışı", "Revizyon kaydı"]},
    "launch": {"name": "Lansman paketi", "price": 42000, "includes": ["Lansman sitesi", "İçerik ve kampanya takvimi", "Teslimat kontrol listesi"]},
}
EXTRAS = {"brand-kit": {"name": "Marka başlangıç kiti", "price": 5000}, "analytics": {"name": "Analitik kurulumu", "price": 3500}, "copy": {"name": "Ek metin paketi", "price": 2500}}
CHECKLIST = {"scope": "Kapsam ve brief", "content": "İçerik ve sürüm", "qa": "Kalite kontrol", "handoff": "Teslim ve kullanım notları"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class APIError(Exception):
    def __init__(self, status: int, message: str, details=None):
        super().__init__(message)
        self.status, self.details = status, details


class NexusEngine:
    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, client TEXT NOT NULL,
                goal TEXT NOT NULL, package_id TEXT NOT NULL, extras_json TEXT NOT NULL,
                amount INTEGER NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
                locked INTEGER NOT NULL, revisions_json TEXT NOT NULL,
                payment_json TEXT, checklist_json TEXT NOT NULL)""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def quote(package_id: str, extra_ids: list[str]) -> dict:
        if package_id not in PACKAGES:
            raise APIError(400, "Paket seçimi geçersiz.")
        if not isinstance(extra_ids, list) or len(set(extra_ids)) != len(extra_ids):
            raise APIError(400, "Ek hizmet listesi geçersiz veya yineleniyor.")
        unknown = sorted(set(extra_ids) - EXTRAS.keys())
        if unknown:
            raise APIError(400, "Bilinmeyen ek hizmet.", {"unknown": unknown})
        package = PACKAGES[package_id]
        extras = [{"id": key, **EXTRAS[key]} for key in extra_ids]
        return {"package": {"id": package_id, **package}, "extras": extras,
                "amount": package["price"] + sum(row["price"] for row in extras), "currency": "TRY"}

    def create_project(self, data: dict) -> dict:
        client = str(data.get("client", "")).strip()
        goal = str(data.get("goal", "")).strip()
        if not client or not goal:
            raise APIError(400, "Müşteri ve hedef alanları zorunludur.")
        if len(client) > 100 or len(goal) > 1200:
            raise APIError(400, "Brief alanı izin verilen uzunluğu aşıyor.")
        q = self.quote(data.get("package", ""), data.get("extras", []))
        pid, now = "NX-" + uuid.uuid4().hex[:12].upper(), utc_now()
        revision = [{"version": 1, "note": "İlk brief ve teklif sürümü", "at": now}]
        checklist = {key: False for key in CHECKLIST}
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                pid, now, client, goal, data["package"], json.dumps(data.get("extras", [])),
                q["amount"], "quote_ready", 1, 0, json.dumps(revision, ensure_ascii=False), None,
                json.dumps(checklist)))
        return self.get_project(pid)

    def get_project(self, project_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise APIError(404, "Proje bulunamadı.")
        q = self.quote(row["package_id"], json.loads(row["extras_json"]))
        payment = json.loads(row["payment_json"]) if row["payment_json"] else None
        return {"id": row["id"], "created_at": row["created_at"], "client": row["client"],
                "goal": row["goal"], "status": row["status"], "version": row["version"],
                "content_locked": bool(row["locked"]), "quote": q,
                "revisions": json.loads(row["revisions_json"]), "payment": payment,
                "checklist": json.loads(row["checklist_json"]), "demo_only": True}

    def add_revision(self, project_id: str, note: str) -> dict:
        note = str(note).strip()
        if not note or len(note) > 500:
            raise APIError(400, "Revizyon notu 1–500 karakter olmalıdır.")
        with self.connect() as db:
            row = db.execute("SELECT version,locked,revisions_json FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None: raise APIError(404, "Proje bulunamadı.")
            if row["locked"]: raise APIError(409, "İçerik sürümü kilitli; yeni revizyon açılamaz.")
            revisions = json.loads(row["revisions_json"])
            version = row["version"] + 1
            revisions.append({"version": version, "note": note, "at": utc_now()})
            db.execute("UPDATE projects SET version=?,revisions_json=? WHERE id=?", (version, json.dumps(revisions, ensure_ascii=False), project_id))
        return self.get_project(project_id)

    def lock_content(self, project_id: str) -> dict:
        with self.connect() as db:
            cur = db.execute("UPDATE projects SET locked=1,status=CASE WHEN payment_json IS NULL THEN 'content_locked' ELSE status END WHERE id=?", (project_id,))
            if cur.rowcount == 0: raise APIError(404, "Proje bulunamadı.")
        return self.get_project(project_id)

    def record_payment(self, project_id: str, data: dict) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT amount,payment_json,locked FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None: raise APIError(404, "Proje bulunamadı.")
            if row["payment_json"]: raise APIError(409, "Bu demo proje için tutar zaten doğrulandı.")
            if not row["locked"]: raise APIError(409, "İçerik sürümü kilitlenmeden teklif tutarı doğrulanamaz.")
            amount, currency = data.get("amount"), data.get("currency")
            if isinstance(amount, bool) or not isinstance(amount, int):
                raise APIError(400, "Ödeme doğrulama tutarı tam sayı TRY olmalıdır.")
            if currency != "TRY" or amount != row["amount"]:
                raise APIError(422, "Bildirilen tutar teklif ile eşleşmiyor.", {"expected_amount": row["amount"], "currency": "TRY"})
            receipt = {"amount": amount, "currency": "TRY", "validated_at": utc_now(), "demo_only": True,
                       "note": "Yerel tutar doğrulama kaydıdır; tahsilat yapılmadı."}
            db.execute("UPDATE projects SET payment_json=?,status='paid_demo' WHERE id=?", (json.dumps(receipt, ensure_ascii=False), project_id))
        return self.get_project(project_id)

    def set_checklist(self, project_id: str, item: str, done: bool) -> dict:
        if item not in CHECKLIST or not isinstance(done, bool):
            raise APIError(400, "Kontrol listesi maddesi veya değeri geçersiz.")
        with self.connect() as db:
            row = db.execute("SELECT status,checklist_json FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None: raise APIError(404, "Proje bulunamadı.")
            if row["status"] not in {"paid_demo", "in_delivery", "delivered"}:
                raise APIError(409, "Teslimat kontrolü tutar doğrulamasından sonra açılır.")
            checklist = json.loads(row["checklist_json"])
            checklist[item] = done
            status = "delivered" if all(checklist.values()) else "in_delivery"
            db.execute("UPDATE projects SET checklist_json=?,status=? WHERE id=?", (json.dumps(checklist), status, project_id))
        return self.get_project(project_id)


def create_server(host="127.0.0.1", port=8765, db_path=DEFAULT_DB):
    engine = NexusEngine(db_path)
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status, body):
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(raw)
        def read_json(self):
            try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            except (ValueError, json.JSONDecodeError): raise APIError(400, "Geçerli JSON gövdesi gerekli.")
        def log_message(self, fmt, *args):
            if os.environ.get("NEXUS_ACCESS_LOG")=="1": super().log_message(fmt,*args)
        def do_GET(self):
            path=urlparse(self.path).path
            try:
                if path == "/api/health": return self.send_json(200,{"ok":True,"demo_only":True})
                if path == "/api/packages": return self.send_json(200,{"packages":PACKAGES,"extras":EXTRAS,"checklist":CHECKLIST})
                if path.startswith("/api/projects/"): return self.send_json(200,engine.get_project(path.rsplit("/",1)[1]))
                if path == "/" or path == "/index.html":
                    raw=(HERE/"index.html").read_bytes(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw); return
                return self.send_json(404,{"error":"Bulunamadı."})
            except APIError as e: return self.send_json(e.status,{"error":str(e),"details":e.details})
        def do_POST(self):
            path=urlparse(self.path).path
            try:
                data=self.read_json()
                if path == "/api/projects": return self.send_json(201,engine.create_project(data))
                if not path.startswith("/api/projects/"): return self.send_json(404,{"error":"Bulunamadı."})
                pieces=path.strip("/").split("/")
                if len(pieces)!=4: return self.send_json(404,{"error":"Bulunamadı."})
                _,_,pid,action=pieces
                if action=="revision": result=engine.add_revision(pid,data.get("note",""))
                elif action=="lock": result=engine.lock_content(pid)
                elif action=="payment": result=engine.record_payment(pid,data)
                elif action=="checklist": result=engine.set_checklist(pid,data.get("item",""),data.get("done"))
                else: return self.send_json(404,{"error":"Bulunamadı."})
                return self.send_json(200,result)
            except APIError as e: return self.send_json(e.status,{"error":str(e),"details":e.details})
            except (TypeError,AttributeError) as e: return self.send_json(400,{"error":"İstek gövdesi beklenen biçimde değil."})
    return ThreadingHTTPServer((host,port),Handler)


def self_check() -> int:
    quote=NexusEngine.quote("growth",["analytics","copy"])
    assert quote["amount"]==30000
    try: NexusEngine.quote("growth",["unknown"])
    except APIError: pass
    else: raise AssertionError("unknown extra accepted")
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest="command",required=True)
    serve=sub.add_parser("serve",help="Yerel web/API demosunu başlat")
    serve.add_argument("--host",default="127.0.0.1"); serve.add_argument("--port",type=int,default=8765)
    serve.add_argument("--db",type=Path,default=DEFAULT_DB); serve.add_argument("--open",action="store_true")
    sub.add_parser("self-check",help="CLI paket ve tutar doğrulamasını çalıştır")
    args=parser.parse_args(argv)
    if args.command=="self-check":
        self_check(); print(json.dumps({"ok":True,"growth_with_analytics_and_copy_try":30000,"demo_only":True},ensure_ascii=False)); return 0
    server=create_server(args.host,args.port,args.db); actual_port=server.server_address[1]
    url=f"http://{args.host}:{actual_port}/"
    print(json.dumps({"url":url,"api":url+"api/health","database":str(args.db.resolve()),"demo_only":True},ensure_ascii=False),flush=True)
    if args.open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0


if __name__=="__main__":
    sys.exit(main())
