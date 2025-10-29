# -*- coding: utf-8 -*-
"""
lab2/files_io.py — надёжная CSV-логика для ЛР2.
- Абсолютные пути (не зависит от CWD)
- CSV с разделителем ';' и BOM (utf-8-sig) — Excel открывает по столбцам
- Хранение: leads.csv; операции: add/list/find/set_status/export
"""

import os
import csv
import time
from pathlib import Path
from typing import List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

# ── База путей относительно самого файла lab2/ ────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

def _resolve_dir(env_value: Optional[str], default_rel: str) -> Path:
    """
    Если в .env дан абсолютный путь — используем его.
    Если относительный — считаем ОТ lab2/, а не от текущей рабочей директории.
    Если нет — берём lab2/<default_rel>.
    """
    if env_value:
        p = Path(env_value)
        return p if p.is_absolute() else (BASE_DIR / p)
    return BASE_DIR / default_rel

DATA_DIR = _resolve_dir(os.getenv("DATA_DIR"), "data")
EXPORT_DIR = _resolve_dir(os.getenv("EXPORT_DIR"), "export")

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

LEADS_CSV = DATA_DIR / "leads.csv"
CSV_DELIM = ";"  # под русскую локаль Excel

COLUMNS = [
    "id",
    "fio",
    "email",
    "gender",
    "status",
    "created",
    "user_id",
    "username",
    "topic",
    "details",
]

ALLOWED_STATUSES = ["new", "in_work", "rejected", "done"]

def _ensure_file():
    if not LEADS_CSV.exists():
        with LEADS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=CSV_DELIM)
            w.writeheader()

def _read_all() -> List[dict]:
    _ensure_file()
    with LEADS_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f, delimiter=CSV_DELIM)
        return [row for row in r]

def _write_all(rows: List[dict]) -> None:
    with LEADS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=CSV_DELIM)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def _next_id(rows: List[dict]) -> int:
    mx = 0
    for r in rows:
        try:
            mx = max(mx, int(r.get("id", "0") or 0))
        except Exception:
            pass
    return mx + 1

def add_lead(
    user_id: int,
    username: str,
    fio: str,
    email: str,
    topic: str,
    details: str,
    gender: Optional[str] = "",
) -> int:
    rows = _read_all()
    new_id = _next_id(rows)
    created = time.strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "id": str(new_id),
        "fio": fio,
        "email": email,
        "gender": gender or "",
        "status": "new",
        "created": created,
        "user_id": str(user_id),
        "username": username or "",
        "topic": topic or "",
        "details": details or "",
    }
    rows.append(row)
    _write_all(rows)
    return new_id

def list_leads(limit: int = 10) -> List[Tuple]:
    rows = _read_all()
    rows_sorted = sorted(rows, key=lambda r: int(r["id"]), reverse=True)
    res = []
    for r in rows_sorted[:limit]:
        res.append((
            int(r["id"]),
            r["fio"],
            r["email"],
            r["gender"],
            r["status"],
            r["created"],
        ))
    return res

def find_leads(query: str) -> List[Tuple]:
    q = (query or "").casefold()
    if not q:
        return []
    rows = _read_all()
    found = []
    for r in rows:
        fio = (r.get("fio", "") or "")
        email = (r.get("email", "") or "")
        if q in fio.casefold() or q in email.casefold():
            found.append((
                int(r["id"]),
                r["fio"],
                r["email"],
                r["gender"],
                r["status"],
                r["created"],
            ))
    found.sort(key=lambda t: int(t[0]), reverse=True)  # свежие сверху
    return found

def set_status(lead_id: int, new_status: str) -> bool:
    if new_status not in ALLOWED_STATUSES:
        return False
    rows = _read_all()
    changed = False
    for r in rows:
        try:
            if int(r["id"]) == int(lead_id):
                r["status"] = new_status
                changed = True
                break
        except Exception:
            continue
    if changed:
        _write_all(rows)
    return changed

def export_csv() -> str:
    _ensure_file()
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = EXPORT_DIR / f"leads_export_{ts}.csv"
    rows = _read_all()
    with dst.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=CSV_DELIM)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return str(dst)
