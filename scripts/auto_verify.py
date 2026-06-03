#!/usr/bin/env python3
"""
Auto-verify events in lampung_monitor.db using two strategies:

1. Trusted sources — Events from BMKG or ANTARA are auto-confirmed.
2. Keyword matching — Events with recovery keywords are confirmed;
   events with only disruption keywords remain pending.

Usage:
    python3 scripts/auto_verify.py              # dry-run (preview only)
    python3 scripts/auto_verify.py --apply      # actually update the DB
"""

import sqlite3
import sys
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "lampung_monitor.db")

# ── Trusted sources (case-insensitive substring match on `source` column) ────
TRUSTED_SOURCES = ["BMKG", "ANTARA"]

# ── Keyword patterns (case-insensitive, checked against title + description) ──
RECOVERY_KEYWORDS = [
    "telah pulih",
    "sudah pulih",
    "sudah normal",
    "kembali normal",
    "telah normal",
    "perbaikan selesai",
    "sudah aktif",
    "telah aktif",
    "sudah beroperasi",
    "telah beroperasi",
    "sudah menyala",
    "telah menyala",
]

DISRUPTION_KEYWORDS = [
    "putus",
    "terganggu",
    "down",
    "mati",
    "gangguan",
    "lumpuh",
    "tidak aktif",
    "tidak bisa",
    "padam",
    "blackout",
]

NOTES_TRUSTED = "Auto-verified: source is trusted (BMKG / ANTARA)."
NOTES_RECOVERY = "Auto-verified: event contains recovery keyword indicating resolution."


def is_trusted_source(source: str | None) -> bool:
    if not source:
        return False
    src_lower = source.lower()
    return any(t.lower() in src_lower for t in TRUSTED_SOURCES)


def has_recovery_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in RECOVERY_KEYWORDS)


def has_disruption_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in DISRUPTION_KEYWORDS)


def auto_verify(apply: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Get all pending events
    cur.execute(
        "SELECT id, title, description, source FROM events WHERE verified_status = 'pending'"
    )
    pending = cur.fetchall()
    total_pending = len(pending)

    confirmed_ids = []
    rejected_ids = []
    skipped_ids = []

    for eid, title, description, source in pending:
        text = f"{title or ''} {description or ''}"
        notes = None
        action = None

        # Strategy 1: Trusted source → auto-confirm
        if is_trusted_source(source):
            action = "confirmed"
            notes = NOTES_TRUSTED

        # Strategy 2: Recovery keywords → auto-confirm
        elif has_recovery_keywords(text):
            action = "confirmed"
            notes = NOTES_RECOVERY

        # If no positive signal, keep pending (disruption keywords don't change status)
        else:
            action = "pending"

        if action == "confirmed":
            confirmed_ids.append((eid, title[:60], notes))
            if apply:
                cur.execute(
                    "UPDATE events SET verified_status = 'confirmed', verified_at = ?, verifier_notes = ? WHERE id = ?",
                    (now, notes, eid),
                )
        else:
            skipped_ids.append(eid)

    if apply:
        conn.commit()

    conn.close()

    # ── Report ──
    print("=" * 60)
    print("AUTO-VERIFY REPORT")
    print("=" * 60)
    print(f"Total pending before run: {total_pending}")
    print(f"Auto-confirmed:            {len(confirmed_ids)}")
    print(f"Remained pending:          {len(skipped_ids)}")
    print(f"Mode: {'APPLIED' if apply else 'DRY RUN (no changes)'}")
    print()

    if confirmed_ids:
        print("── Confirmed events ──")
        for eid, title, notes in confirmed_ids:
            print(f"  ID {eid:>3d}: {title}")
        print()

    print(f"── {len(skipped_ids)} events remain pending (no trusted source or recovery keyword found) ──")
    print()
    print("=" * 60)

    return {
        "total_pending": total_pending,
        "confirmed": len(confirmed_ids),
        "remaining_pending": len(skipped_ids),
        "applied": apply,
    }


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    auto_verify(apply=apply)
