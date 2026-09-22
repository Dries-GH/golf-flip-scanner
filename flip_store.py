
"""Persistence layer: analyses log + deal pipeline (SQLite)."""
import os
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flipgolf.db")


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS analyses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    TEXT NOT NULL,
            url           TEXT,
            source        TEXT,
            brand         TEXT,
            model         TEXT,
            category      TEXT,
            specs         TEXT,
            condition     TEXT,
            listing_type  TEXT,
            price         REAL,
            low           REAL,
            high          REAL,
            likely        REAL,
            confidence    REAL,
            liquidity     TEXT,
            buffer        REAL,
            ceiling       REAL,
            profit        REAL,
            roi           REAL,
            verdict       TEXT,
            summary       TEXT,
            payload       TEXT
        );

        CREATE TABLE IF NOT EXISTS pipeline (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER,
            created_at  TEXT NOT NULL,
            status      TEXT NOT NULL,          -- watching | bought | sold | dropped
            item        TEXT,
            url         TEXT,
            ceiling     REAL,
            est_resale  REAL,
            buy_price   REAL,
            buy_date    TEXT,
            sold_price  REAL,
            sold_date   TEXT,
            costs       REAL DEFAULT 0,
            notes       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_pipe_status ON pipeline(status);
        CREATE INDEX IF NOT EXISTS idx_an_created ON analyses(created_at);
        """)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_analysis(rec, payload=None):
    cols = ["created_at","url","source","brand","model","category","specs","condition",
            "listing_type","price","low","high","likely","confidence","liquidity",
            "buffer","ceiling","profit","roi","verdict","summary"]
    vals = [now()] + [rec.get(k) for k in cols[1:]]
    with _conn() as c:
        cur = c.execute(
            f"INSERT INTO analyses ({','.join(cols)},payload) VALUES ({','.join('?'*len(cols))},?)",
            vals + [json.dumps(payload or {}, ensure_ascii=False)])
        return cur.lastrowid


def add_to_pipeline(item, url, ceiling, est_resale, analysis_id=None, status="watching", notes=""):
    with _conn() as c:
        ex = c.execute("SELECT id FROM pipeline WHERE url=? AND status!='dropped'", (url,)).fetchone()
        if ex:
            return ex["id"], False
        cur = c.execute("""INSERT INTO pipeline
            (analysis_id,created_at,status,item,url,ceiling,est_resale,notes)
            VALUES (?,?,?,?,?,?,?,?)""",
            (analysis_id, now(), status, item, url, ceiling, est_resale, notes))
        return cur.lastrowid, True


def update_pipeline(pid, **kw):
    if not kw:
        return
    sets = ",".join(f"{k}=?" for k in kw)
    with _conn() as c:
        c.execute(f"UPDATE pipeline SET {sets} WHERE id=?", list(kw.values()) + [pid])


def delete_pipeline(pid):
    with _conn() as c:
        c.execute("DELETE FROM pipeline WHERE id=?", (pid,))


def pipeline(status=None):
    q = "SELECT * FROM pipeline"
    a = []
    if status:
        q += " WHERE status=?"
        a.append(status)
    q += " ORDER BY datetime(created_at) DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, a).fetchall()]


def analyses(limit=200):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM analyses ORDER BY datetime(created_at) DESC LIMIT ?", (limit,)).fetchall()]


def kpis():
    """Business metrics for the dashboard."""
    with _conn() as c:
        watching = c.execute("SELECT COUNT(*) n FROM pipeline WHERE status='watching'").fetchone()["n"]
        bought = c.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(buy_price),0) s FROM pipeline WHERE status='bought'").fetchone()
        sold = c.execute("""SELECT COUNT(*) n,
                   COALESCE(SUM(sold_price),0) rev,
                   COALESCE(SUM(buy_price),0) cost,
                   COALESCE(SUM(costs),0) fees
            FROM pipeline WHERE status='sold'""").fetchone()
        n_an = c.execute("SELECT COUNT(*) n FROM analyses").fetchone()["n"]
        # estimate accuracy: sold price vs est_resale at time of listing
        acc = c.execute("""SELECT est_resale, sold_price FROM pipeline
                           WHERE status='sold' AND est_resale>0 AND sold_price>0""").fetchall()
        days = c.execute("""SELECT buy_date, sold_date FROM pipeline
                            WHERE status='sold' AND buy_date IS NOT NULL AND sold_date IS NOT NULL""").fetchall()

    realized = sold["rev"] - sold["cost"] - sold["fees"]
    roi = (realized / sold["cost"] * 100) if sold["cost"] else 0.0

    err = None
    if acc:
        err = sum(abs(r["sold_price"] - r["est_resale"]) / r["est_resale"] for r in acc) / len(acc) * 100

    hold = None
    if days:
        tot, n = 0, 0
        for r in days:
            try:
                d = (datetime.fromisoformat(r["sold_date"]) - datetime.fromisoformat(r["buy_date"])).days
                tot += max(d, 0); n += 1
            except Exception:
                pass
        hold = tot / n if n else None

    return {"watching": watching, "bought_n": bought["n"], "capital": bought["s"],
            "sold_n": sold["n"], "revenue": sold["rev"], "realized": realized,
            "roi": roi, "analyses": n_an, "est_error": err, "hold_days": hold}
