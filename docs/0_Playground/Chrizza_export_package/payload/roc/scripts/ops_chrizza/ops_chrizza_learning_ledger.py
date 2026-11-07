"""Chrizza's call ledger: register forecasts, score them, compute Brier and the conviction cap.

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (operator intelligence publishing)
    Classifier    : CC-Bear
    Lock status   : UNLOCKED — awaiting Agent Manager ratification

This is the Reflect stage of the OODA loop. Every dossier call is a dated,
falsifiable probability. Once a call's resolve_by date passes it is scored, and
the track record sets the highest conviction band the next dossier may use.
Until enough calls are scored, conviction stays capped at "medium".

CLI:
    register --date YYYYMMDD                         add the dossier's calls (idempotent)
    due      --as-of YYYY-MM-DD                      list pending calls past resolve_by
    score    --id CALL_ID --outcome yes|no --evidence "..."
    stats                                            track record and current cap
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    LEDGER_PATH,
    SCHEMA_LEDGER,
    content_path,
    load_json,
    save_json,
)

BAND_RANK = {"low": 0, "medium": 1, "high": 2}
MIN_SCORED_FOR_CAP_CHANGE = 10


def conviction_band(p: float) -> str:
    """Map a probability to a conviction band by its distance from a coin flip."""
    distance = abs(p - 0.5)
    if distance < 0.15:
        return "low"
    if distance < 0.30:
        return "medium"
    return "high"


def empty_ledger() -> dict[str, Any]:
    """Return a new, empty ledger document."""
    return {"schema": SCHEMA_LEDGER, "calls": []}


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    """Load the ledger, or return an empty one if the file does not exist yet."""
    return load_json(path) if path.exists() else empty_ledger()


def register_calls(ledger: dict[str, Any], content: dict[str, Any], now_utc: str) -> int:
    """Add the dossier's calls to the ledger, skipping IDs already present. Returns the count added."""
    known = {c["id"] for c in ledger["calls"]}
    added = 0
    for call in content.get("calls", []):
        if call["id"] in known:
            continue
        ledger["calls"].append({
            "id": call["id"],
            "dossier_id": content["dossier_id"],
            "topic": call["topic"],
            "proposition": call["proposition"],
            "p": call["p"],
            "band": conviction_band(call["p"]),
            "resolve_by": call["resolve_by"],
            "resolution_source": call["resolution_source"],
            "registered_at_utc": now_utc,
            "status": "pending",
            "outcome": None,
            "scored_at_utc": None,
            "evidence": None,
        })
        added += 1
    return added


def score_call(ledger: dict[str, Any], call_id: str, outcome: bool, evidence: str, now_utc: str) -> dict:
    """Record the outcome of a pending call. Raises if unknown or already scored."""
    for call in ledger["calls"]:
        if call["id"] != call_id:
            continue
        if call["status"] != "pending":
            raise ValueError(f"{call_id} already scored")
        if not evidence.strip():
            raise ValueError("scoring requires evidence")
        call.update(status="scored", outcome=outcome, scored_at_utc=now_utc, evidence=evidence)
        return call
    raise KeyError(call_id)


def due_calls(ledger: dict[str, Any], as_of: date) -> list[dict]:
    """Pending calls whose resolve_by date is on or before as_of."""
    return [
        c for c in ledger["calls"]
        if c["status"] == "pending" and datetime.strptime(c["resolve_by"], "%Y-%m-%d").date() <= as_of
    ]


def stats(ledger: dict[str, Any]) -> dict[str, Any]:
    """Track record: scored count, hit rate, Brier score and pending count."""
    scored = [c for c in ledger["calls"] if c["status"] == "scored"]
    n = len(scored)
    hits = sum(1 for c in scored if (c["p"] > 0.5) == bool(c["outcome"]))
    brier = sum((c["p"] - (1.0 if c["outcome"] else 0.0)) ** 2 for c in scored) / n if n else None
    return {
        "n_scored": n,
        "hits": hits,
        "hit_rate": hits / n if n else None,
        "brier": brier,
        "pending": sum(1 for c in ledger["calls"] if c["status"] == "pending"),
    }


def conviction_cap(st: dict[str, Any]) -> str:
    """Highest conviction band the next dossier may publish, earned from the track record."""
    if st["n_scored"] < MIN_SCORED_FOR_CAP_CHANGE:
        return "medium"
    if st["brier"] > 0.25 or st["hit_rate"] < 0.5:
        return "low"
    if st["brier"] <= 0.20 and st["hit_rate"] >= 0.55:
        return "high"
    return "medium"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_reg = sub.add_parser("register")
    p_reg.add_argument("--date", required=True)
    p_due = sub.add_parser("due")
    p_due.add_argument("--as-of", required=True)
    p_score = sub.add_parser("score")
    p_score.add_argument("--id", required=True)
    p_score.add_argument("--outcome", required=True, choices=("yes", "no"))
    p_score.add_argument("--evidence", required=True)
    sub.add_parser("stats")
    args = parser.parse_args(argv)

    ledger = load_ledger()
    if args.cmd == "register":
        added = register_calls(ledger, load_json(content_path(args.date)), _now())
        save_json(LEDGER_PATH, ledger)
        print(f"registered {added} new call(s); ledger holds {len(ledger['calls'])}")
    elif args.cmd == "due":
        due = due_calls(ledger, datetime.strptime(args.as_of, "%Y-%m-%d").date())
        for c in due:
            print(f"{c['id']}  p={c['p']:.2f}  resolve_by={c['resolve_by']}  {c['proposition']}")
        print(f"{len(due)} call(s) due for scoring")
    elif args.cmd == "score":
        call = score_call(ledger, args.id, args.outcome == "yes", args.evidence, _now())
        save_json(LEDGER_PATH, ledger)
        print(f"scored {call['id']}: outcome={args.outcome}")
    else:
        st = stats(ledger)
        print({**st, "conviction_cap": conviction_cap(st)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
