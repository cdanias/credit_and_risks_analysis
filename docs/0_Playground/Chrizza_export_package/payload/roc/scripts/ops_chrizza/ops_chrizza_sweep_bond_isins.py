"""Deterministic Gap G5 sweeper: European exchange Eurobond & Reg S ISIN clean bid-ask quotes.

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (live Eurobond ISIN order-book telemetry)
    Classifier    : CC-Bear · RC-Butterfly with roc/scripts/ops_chrizza
    Lock status   : UNLOCKED — awaiting Agent Manager ratification
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    SCHEMA_BOND_ISINS,
    WEB_USER_AGENT,
    bond_isins_path,
    dec_round,
    load_watchlist,
    ROOT,
    save_json,
    seal_payload,
)

ONVISTA_QUERY_URL = "https://api.onvista.de/api/v1/instruments/query?searchValue={isin}"
ONVISTA_SNAP_URL = "https://api.onvista.de/api/v1/instruments/BOND/{entity_id}/snapshot"
PREFERRED_EXCHANGES = ("STU", "FRA", "_GET", "TGT", "MUN", "BER", "HAN")
HTTP_TIMEOUT_SEC = 15


def _http_get_json(url: str) -> dict[str, Any]:
    """Fetch JSON over HTTPS with explicit timeout and contextualized exception chaining."""
    req = urllib.request.Request(url, headers={"User-Agent": WEB_USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Eurobond API request failed for {url}: {exc}") from exc


def _select_best_quote(snap: dict[str, Any]) -> dict[str, Any]:
    """Select the freshest two-sided quote across German/European MTF & regulated bond venues."""
    candidates: list[dict[str, Any]] = []
    q_list = snap.get("quoteList", {}).get("list", [])
    if isinstance(q_list, list):
        candidates.extend(q for q in q_list if isinstance(q, dict))
    primary = snap.get("quote")
    if isinstance(primary, dict):
        candidates.append(primary)
    if not candidates:
        raise RuntimeError("Bond snapshot contained no quote entries")

    def _rank(q: dict[str, Any]) -> tuple[int, int, str]:
        bid = q.get("bid")
        ask = q.get("ask")
        two_sided = int(bid is not None and ask is not None and float(bid) > 0 and float(ask) > 0)
        ex_code = str(q.get("market", {}).get("codeExchange") or q.get("market", {}).get("codeMarket") or "")
        pref_score = (
            len(PREFERRED_EXCHANGES) - PREFERRED_EXCHANGES.index(ex_code)
            if ex_code in PREFERRED_EXCHANGES
            else 0
        )
        dt = str(q.get("datetimeBid") or q.get("datetimeLast") or "")
        return (two_sided, pref_score, dt)

    return max(candidates, key=_rank)


def fetch_bond_isin_quote(spec: dict[str, str]) -> dict[str, Any]:
    """Resolve ISIN to instrument snapshot and compute Decimal clean bid/ask/mid & 1Y drawdown."""
    isin = spec["isin"].strip().upper()
    q_doc = _http_get_json(ONVISTA_QUERY_URL.format(isin=urllib.parse.quote(isin)))
    matches = [x for x in q_doc.get("list", []) if x.get("entityType") == "BOND"]
    if not matches:
        raise RuntimeError(f"No European exchange BOND listing resolved for ISIN {isin}")
    entity_id = str(matches[0]["entityValue"])
    snap = _http_get_json(ONVISTA_SNAP_URL.format(entity_id=urllib.parse.quote(entity_id)))
    best_q = _select_best_quote(snap)
    inst = snap.get("instrument", {})
    mkt = best_q.get("market", {})

    bid = Decimal(str(best_q["bid"])) if best_q.get("bid") is not None else None
    ask = Decimal(str(best_q["ask"])) if best_q.get("ask") is not None else None
    last = Decimal(str(best_q["last"])) if best_q.get("last") is not None else None
    high_1y = Decimal(str(best_q["highPrice1Year"])) if best_q.get("highPrice1Year") is not None else None
    low_1y = Decimal(str(best_q["lowPrice1Year"])) if best_q.get("lowPrice1Year") is not None else None

    if bid is not None and ask is not None and bid > Decimal("0") and ask > Decimal("0"):
        mid = (bid + ask) / Decimal("2")
        spread_pts = ask - bid
    else:
        mid = last if last is not None else (bid or ask or Decimal("0"))
        spread_pts = Decimal("0")

    drawdown_1y_pct: float | None = None
    if high_1y is not None and high_1y > Decimal("0") and mid > Decimal("0"):
        drawdown_1y_pct = dec_round(Decimal("100") * (mid - high_1y) / high_1y, "0.02")

    return {
        "isin": isin,
        "issuer": spec["issuer"],
        "label": spec["label"],
        "exchange_name": inst.get("name") or spec["label"],
        "seniority": spec["seniority"],
        "jurisdiction": spec["jurisdiction"],
        "theme": spec["theme"],
        "venue": mkt.get("name") or mkt.get("nameExchange") or "EUR_EXCHANGE",
        "currency": best_q.get("isoCurrency") or "EUR",
        "bid": dec_round(bid, "0.03") if bid is not None else None,
        "ask": dec_round(ask, "0.03") if ask is not None else None,
        "mid": dec_round(mid, "0.03"),
        "bid_ask_spread_pts": dec_round(spread_pts, "0.03"),
        "last": dec_round(last, "0.03") if last is not None else None,
        "high_1y": dec_round(high_1y, "0.03") if high_1y is not None else None,
        "low_1y": dec_round(low_1y, "0.03") if low_1y is not None else None,
        "drawdown_1y_pct": drawdown_1y_pct,
        "volume_bid": float(best_q["volumeBid"]) if best_q.get("volumeBid") is not None else None,
        "quote_timestamp_utc": best_q.get("datetimeBid") or best_q.get("datetimeLast"),
    }


def theme_summary(bonds: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate count, average mid, minimum bid and maximum ask per watch-list theme."""
    out: dict[str, dict[str, Any]] = {}
    for theme in dict.fromkeys(b["theme"] for b in bonds):
        group = [b for b in bonds if b["theme"] == theme]
        mids = [Decimal(str(b["mid"])) for b in group]
        out[theme] = {
            "count": len(group),
            "avg_mid": dec_round(sum(mids) / Decimal(len(mids)), "0.02") if mids else None,
            "min_bid": min((b["bid"] for b in group if b["bid"] is not None), default=None),
            "max_ask": max((b["ask"] for b in group if b["ask"] is not None), default=None),
        }
    return out


def sweep_bond_isins(stamp: str) -> dict[str, Any]:
    """Sweep all benchmark watchlist Eurobond ISINs and write SHA-256 sealed JSON."""
    wl = load_watchlist()
    bonds = [fetch_bond_isin_quote(spec) for spec in wl["bonds"]]

    # Generic per-theme aggregates: no issuer or topic literals (themes come from the watchlist).
    summary = {
        "total_isins_quoted": len(bonds),
        "theme_summary": theme_summary(bonds),
        "lowest_priced_isin": min(bonds, key=lambda x: float(x["mid"]))["isin"] if bonds else None,
        "lowest_priced_mid": min(bonds, key=lambda x: float(x["mid"]))["mid"] if bonds else None,
    }

    payload: dict[str, Any] = {
        "schema": SCHEMA_BOND_ISINS,
        "date": stamp,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "euro_exchange_isin_quotes",
        "summary": summary,
        "bonds": bonds,
    }
    payload["sha256"] = seal_payload(payload)
    out_path = bond_isins_path(stamp)
    save_json(out_path, payload)
    print(
        f"swept & sealed {len(bonds)} benchmark Eurobond ISIN quote(s) in "
        f"{out_path.relative_to(ROOT).as_posix()} sha256={payload['sha256'][:16]}…"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    args = ap.parse_args(argv)
    sweep_bond_isins(args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

