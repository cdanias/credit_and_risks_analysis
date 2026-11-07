"""Deterministic Gap G4 (+ G3) sweeper: FRED H.8 NDFI bank loans, credit OAS & SEC EDGAR BDC PIK XBRL.

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (statutory & macro credit telemetry)
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
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    SCHEMA_NBFI_BDC,
    SEC_USER_AGENT,
    dec_round,
    load_provider_key,
    load_watchlist,
    nbfi_bdc_path,
    ROOT,
    save_json,
    seal_payload,
)

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
EDGAR_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
EDGAR_SUB_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
HTTP_TIMEOUT_SEC = 20


def _http_get_json(url: str, headers: dict[str, str], timeout: int = HTTP_TIMEOUT_SEC) -> dict[str, Any]:
    """Fetch JSON over HTTPS with explicit timeout and contextualized error chaining."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET failed for {url}: {exc}") from exc


def fetch_fred_series(fred_key: str, series_specs: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Fetch latest valid observation and prior observation for each configured FRED series."""
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    out: dict[str, dict[str, Any]] = {}
    for spec in series_specs:
        sid = spec["series_id"]
        params = urllib.parse.urlencode({
            "series_id": sid,
            "api_key": fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "10",
        })
        doc = _http_get_json(f"{FRED_OBS_URL}?{params}", headers=headers)
        valid = [o for o in doc.get("observations", []) if o.get("value") not in (None, ".", "")]
        if not valid:
            raise RuntimeError(f"FRED series {sid} returned zero valid observations")
        latest = Decimal(str(valid[0]["value"]))
        prior = Decimal(str(valid[1]["value"])) if len(valid) > 1 else latest
        delta = latest - prior
        out[sid] = {
            "series_id": sid,
            "label": spec["label"],
            "unit": spec["unit"],
            "as_of": valid[0]["date"],
            "value": dec_round(latest, "0.01"),
            "prior_as_of": valid[1]["date"] if len(valid) > 1 else valid[0]["date"],
            "prior_value": dec_round(prior, "0.01"),
            "delta": dec_round(delta, "0.01"),
        }
    return out


def _window_rows(gaap: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    """Extract dated USD 10-Q/10-K duration rows for an XBRL tag."""
    rows = gaap.get(tag, {}).get("units", {}).get("USD", [])
    clean: list[dict[str, Any]] = []
    for r in rows:
        if r.get("form") not in ("10-Q", "10-K") or not r.get("start") or not r.get("end"):
            continue
        if r["end"] < "2025-09-30":
            continue
        days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
        clean.append({
            "start": r["start"],
            "end": r["end"],
            "days": days,
            "val": Decimal(str(r["val"])),
            "form": r["form"],
            "filed": r.get("filed", ""),
            "accn": r.get("accn", ""),
        })
    return clean


def _dedup_by_window(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Keep the most recently filed fact for each (start, end) window."""
    by_win: dict[tuple[str, str], dict[str, Any]] = {}
    for r in sorted(rows, key=lambda x: (x["end"], x["filed"])):
        by_win[(r["start"], r["end"])] = r
    return by_win


def _resolve_window_metric(
    win_map: dict[tuple[str, str], dict[str, Any]],
    q_key: tuple[str, str],
) -> tuple[Decimal | None, str]:
    """Resolve a QTD USD amount either directly on q_key or via 90-day YTD delta ending on q_key[1]."""
    if q_key in win_map:
        return win_map[q_key]["val"], "QTD_DIRECT"
    q_start, q_end = q_key
    ytd_candidates = [k for k in win_map if k[1] == q_end and k[0] < q_start]
    for ytd_key in sorted(ytd_candidates, key=lambda k: k[0]):
        ytd_days = win_map[ytd_key]["days"]
        prior_ytd = [
            k for k in win_map
            if k[0] == ytd_key[0] and k[1] < q_end and 75 <= (ytd_days - win_map[k]["days"]) <= 105
        ]
        if prior_ytd:
            prev_key = sorted(prior_ytd, key=lambda k: k[1])[-1]
            delta = win_map[ytd_key]["val"] - win_map[prev_key]["val"]
            if delta >= Decimal("0"):
                return delta, "YTD_DELTA_IMPLIED_QTD"
    return None, "UNREPORTED"


def analyze_bdc_xbrl(spec: dict[str, str]) -> dict[str, Any]:
    """Compute matched-duration QTD PIK Interest, PIK Dividend & Total PIK % for a public BDC."""
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    cik = spec["cik"].zfill(10)
    doc = _http_get_json(EDGAR_FACTS_URL.format(cik=cik), headers=headers)
    gaap = doc.get("facts", {}).get("us-gaap", {})

    gross_tag = next(
        (t for t in ("GrossInvestmentIncomeOperating", "InvestmentIncomeInterestAndDividend", "Revenues") if t in gaap),
        None,
    )
    if not gross_tag:
        raise RuntimeError(f"BDC {spec['symbol']} ({cik}) missing gross investment income XBRL tag")

    gross_wins = _dedup_by_window(_window_rows(gaap, gross_tag))
    qtd_gross = [v for v in gross_wins.values() if 75 <= v["days"] <= 105]
    if not qtd_gross:
        raise RuntimeError(f"BDC {spec['symbol']} ({cik}) has no ~90-day QTD gross income rows")
    latest_q = sorted(qtd_gross, key=lambda x: (x["end"], x["filed"]))[-1]
    q_key = (latest_q["start"], latest_q["end"])
    denom_usd: Decimal = latest_q["val"]

    int_op = _dedup_by_window(_window_rows(gaap, "InterestIncomeOperatingPaidInKind"))
    div_op = _dedup_by_window(_window_rows(gaap, "DividendIncomeOperatingPaidInKind"))
    comb_op = _dedup_by_window(_window_rows(gaap, "InterestAndDividendIncomeOperatingPaidInKind"))
    int_cf = _dedup_by_window(_window_rows(gaap, "PaidInKindInterest"))

    pik_int_usd, int_basis = _resolve_window_metric(int_op, q_key)
    if pik_int_usd is None:
        pik_int_usd, int_basis = _resolve_window_metric(int_cf, q_key)
    pik_div_usd, div_basis = _resolve_window_metric(div_op, q_key)
    pik_comb_usd, comb_basis = _resolve_window_metric(comb_op, q_key)

    pik_usd: Decimal | None = None
    basis = "UNREPORTED_IN_XBRL"
    pik_tag = "NONE"

    if pik_comb_usd is not None:
        pik_usd = pik_comb_usd
        basis = comb_basis
        pik_tag = "InterestAndDividendIncomeOperatingPaidInKind"
    elif pik_int_usd is not None or pik_div_usd is not None:
        pik_usd = (pik_int_usd or Decimal("0")) + (pik_div_usd or Decimal("0"))
        basis = int_basis if pik_int_usd is not None else div_basis
        pik_tag = (
            "InterestIncomeOperatingPaidInKind+DividendIncomeOperatingPaidInKind"
            if pik_div_usd is not None
            else "InterestIncomeOperatingPaidInKind"
        )

    pik_int_pct = (
        dec_round(Decimal("100") * pik_int_usd / denom_usd, "0.02")
        if pik_int_usd is not None and denom_usd > Decimal("0")
        else None
    )
    pik_div_pct = (
        dec_round(Decimal("100") * pik_div_usd / denom_usd, "0.02")
        if pik_div_usd is not None and denom_usd > Decimal("0")
        else None
    )
    pik_share_pct = (
        dec_round(Decimal("100") * pik_usd / denom_usd, "0.02")
        if pik_usd is not None and denom_usd > Decimal("0")
        else None
    )

    return {
        "symbol": spec["symbol"],
        "cik": cik,
        "name": doc.get("entityName") or spec["name"],
        "latest_period_end": latest_q["end"],
        "latest_form": latest_q["form"],
        "latest_filed": latest_q["filed"],
        "latest_GrossIncome_qtd_usd_m": dec_round(denom_usd / Decimal("1000000"), "0.02"),
        "pik_interest_usd_m": dec_round(pik_int_usd / Decimal("1000000"), "0.02") if pik_int_usd is not None else None,
        "pik_dividend_usd_m": dec_round(pik_div_usd / Decimal("1000000"), "0.02") if pik_div_usd is not None else None,
        "pik_usd_m": dec_round(pik_usd / Decimal("1000000"), "0.02") if pik_usd is not None else None,
        "pik_denom_usd_m": dec_round(denom_usd / Decimal("1000000"), "0.02"),
        "pik_interest_share_pct": pik_int_pct,
        "pik_dividend_share_pct": pik_div_pct,
        "pik_share_pct": pik_share_pct,
        "pik_calculation_basis": basis,
        "pik_xbrl_tag": pik_tag,
        "is_q3_2026_filed": latest_q["end"] >= "2026-09-30",
        "triggers_call_C_20261029_01": bool(
            latest_q["end"] >= "2026-09-30" and pik_share_pct is not None and pik_share_pct >= 10.0
        ),
    }


def fetch_warehouse_bank_filings(bank_specs: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Capture latest Form 10-Q / 10-K NBFI & VIE footnote filing metadata for top warehouse banks."""
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    records: list[dict[str, Any]] = []
    for spec in bank_specs:
        cik = spec["cik"].zfill(10)
        sub = _http_get_json(EDGAR_SUB_URL.format(cik=cik), headers=headers)
        rec = sub.get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        dates = rec.get("filingDate", [])
        accns = rec.get("accessionNumber", [])
        docs = rec.get("primaryDocument", [])
        hit = next(
            (
                (f, d, a, doc_name)
                for f, d, a, doc_name in zip(forms, dates, accns, docs)
                if f in ("10-Q", "10-K")
            ),
            None,
        )
        if hit:
            f, d, a, doc_name = hit
            cik_int = cik.lstrip("0")
            url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{a.replace('-', '')}/{doc_name}"
            records.append({
                "symbol": spec["symbol"],
                "cik": cik,
                "name": sub.get("name") or spec["name"],
                "latest_periodic_form": f,
                "filing_date": d,
                "accession": a,
                "archive_url": url,
            })
    return records


def sweep_nbfi_and_bdc(stamp: str) -> dict[str, Any]:
    """Execute full Gap G4 (+ G3) sweep and write SHA-256 sealed JSON."""
    wl = load_watchlist()
    fred_key = load_provider_key("fred", "api_key")
    fred = fetch_fred_series(fred_key, wl["fred_series"])

    ndfi_bn = Decimal(str(fred["LNFACBW027SBOG"]["value"]))
    totll_bn = Decimal(str(fred["TOTLL"]["value"]))
    eur_hy = Decimal(str(fred["BAMLHE00EHYIOAS"]["value"]))
    us_hy = Decimal(str(fred["BAMLH0A0HYM2"]["value"]))
    us_bb = Decimal(str(fred["BAMLH0A1HYBB"]["value"]))
    us_ccc = Decimal(str(fred["BAMLH0A3HYC"]["value"]))

    derived = {
        "ndfi_share_of_total_bank_loans_pct": dec_round(Decimal("100") * ndfi_bn / totll_bn, "0.02"),
        "eur_minus_us_hy_oas_bp": dec_round(Decimal("100") * (eur_hy - us_hy), "0.1"),
        "us_ccc_minus_bb_oas_bp": dec_round(Decimal("100") * (us_ccc - us_bb), "0.1"),
        "us_ccc_minus_broad_hy_oas_bp": dec_round(Decimal("100") * (us_ccc - us_hy), "0.1"),
    }

    bdc_records = [analyze_bdc_xbrl(spec) for spec in wl["bdcs"]]
    scored_bdcs = [b["pik_share_pct"] for b in bdc_records if b["pik_share_pct"] is not None]
    avg_pik = (
        dec_round(sum(Decimal(str(x)) for x in scored_bdcs) / Decimal(len(scored_bdcs)), "0.02")
        if scored_bdcs
        else None
    )
    max_bdc = max(
        (b for b in bdc_records if b["pik_share_pct"] is not None),
        key=lambda x: float(x["pik_share_pct"]),
        default=None,
    )

    banks = fetch_warehouse_bank_filings(wl["warehouse_banks"])

    payload: dict[str, Any] = {
        "schema": SCHEMA_NBFI_BDC,
        "date": stamp,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": ["fred_credit_oas_h8", "sec_edgar_xbrl_nport"],
        "fred_series": fred,
        "fred_derived": derived,
        "bdc_pik_summary": {
            "monitored_count": len(bdc_records),
            "xbrl_pik_reported_count": len(scored_bdcs),
            "equal_weighted_pik_share_pct": avg_pik,
            "highest_pik_bdc": max_bdc["symbol"] if max_bdc else None,
            "highest_pik_share_pct": max_bdc["pik_share_pct"] if max_bdc else None,
            "q3_2026_filers_to_date": [b["symbol"] for b in bdc_records if b["is_q3_2026_filed"]],
            "call_C_20261029_01_triggered": any(b["triggers_call_C_20261029_01"] for b in bdc_records),
        },
        "bdc_records": bdc_records,
        "warehouse_bank_filings": banks,
    }
    payload["sha256"] = seal_payload(payload)
    out_path = nbfi_bdc_path(stamp)
    save_json(out_path, payload)
    print(
        f"swept & sealed FRED NDFI/OAS + {len(bdc_records)} BDC XBRL PIK records in "
        f"{out_path.relative_to(ROOT).as_posix()} sha256={payload['sha256'][:16]}…"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    args = ap.parse_args(argv)
    sweep_nbfi_and_bdc(args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
