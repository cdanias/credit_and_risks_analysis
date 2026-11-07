"""Deterministic Gap G1 sweeper: SEC EDGAR Form NPORT-P deal-level CLO tranches & European trustee drop-in.

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (deal-by-deal CLO tranche & trustee telemetry)
    Classifier    : CC-Bear · RC-Butterfly with roc/scripts/ops_chrizza
    Lock status   : UNLOCKED — awaiting Agent Manager ratification
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    INBOX_TRUSTEE_DIR,
    ROOT,
    SCHEMA_CLO_TRANCHES,
    SEC_USER_AGENT,
    clo_tranches_path,
    dec_round,
    load_json,
    load_watchlist,
    save_json,
    seal_payload,
    sha256_file,
)

EDGAR_SUB_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVE_XML_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/primary_doc.xml"
SERIES_RE = re.compile(r"<seriesName>(.*?)</seriesName>")
HTTP_TIMEOUT_SEC = 25


def _http_get_bytes(url: str, max_bytes: int | None = None) -> bytes:
    """Fetch bytes over HTTPS with explicit timeout and optional prefix cap."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json, application/xml, text/xml, */*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
            return resp.read(max_bytes) if max_bytes is not None else resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"SEC EDGAR fetch failed for {url}: {exc}") from exc


def _manager_shelf(deal_name: str) -> str:
    """Extract canonical CLO manager shelf prefix from a deal issuer name."""
    cleaned = re.sub(r"\s+(CLO|BSL|Euro|Middle Market|MM|Static|Funding|Ltd\.?|LLC|PLC|DAC)\b.*$", "", deal_name, flags=re.I)
    tokens = cleaned.strip().split()
    return " ".join(tokens[:2]) if tokens else deal_name.strip()


def _discover_latest_series_nports(cik: str, target_series: dict[str, str]) -> dict[str, tuple[str, str, str]]:
    """Map each target ETF series name to its latest (symbol, filing_date, accession)."""
    cik_pad = cik.zfill(10)
    cik_int = cik_pad.lstrip("0")
    sub = json.loads(_http_get_bytes(EDGAR_SUB_URL.format(cik=cik_pad)).decode("utf-8"))
    rec = sub.get("filings", {}).get("recent", {})
    nports = [
        (d, a)
        for f, d, a in zip(rec.get("form", []), rec.get("filingDate", []), rec.get("accessionNumber", []))
        if f == "NPORT-P"
    ]
    found: dict[str, tuple[str, str, str]] = {}
    for filing_date, acc in nports[:30]:
        if len(found) == len(target_series):
            break
        head_url = EDGAR_ARCHIVE_XML_URL.format(cik_int=cik_int, acc_nodash=acc.replace("-", ""))
        head_txt = _http_get_bytes(head_url, max_bytes=36000).decode("utf-8", errors="ignore")
        m = SERIES_RE.search(head_txt)
        if not m:
            continue
        s_name = m.group(1).strip()
        if s_name in target_series and s_name not in found:
            found[s_name] = (target_series[s_name], filing_date, acc)
    return found


def _parse_nport_clo_series(
    cik: str, series_name: str, symbol: str, filing_date: str, accession: str
) -> dict[str, Any]:
    """Stream-parse Form NPORT-P XML for a CLO ETF and compute Decimal deal-level tranche metrics."""
    cik_int = cik.zfill(10).lstrip("0")
    xml_url = EDGAR_ARCHIVE_XML_URL.format(cik_int=cik_int, acc_nodash=accession.replace("-", ""))
    raw_bytes = _http_get_bytes(xml_url)

    rep_pd_date = ""
    net_assets = Decimal("0")
    tranches: list[dict[str, Any]] = []
    shelf_par: Counter[str] = Counter()

    for _, elem in ET.iterparse(io.BytesIO(raw_bytes), events=("end",)):
        tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag
        if tag == "repPdDate" and elem.text:
            rep_pd_date = elem.text.strip()
        elif tag == "netAssets" and elem.text:
            net_assets = Decimal(elem.text.strip())
        elif tag == "invstOrSec":
            # Strip namespaces on children of this holding only, then clear element to bound RAM.
            for ch in elem.iter():
                if "}" in ch.tag:
                    ch.tag = ch.tag.split("}", 1)[1]
            asset_cat = (elem.findtext("assetCat") or "").strip()
            name = (elem.findtext("name") or "").strip()
            title = (elem.findtext("title") or "").strip()
            units = (elem.findtext("units") or "").strip()
            if units == "PA" and (asset_cat == "ABS-CBDO" or "CLO" in f"{name} {title}".upper()):
                bal_str = elem.findtext("balance")
                val_str = elem.findtext("valUSD")
                if bal_str and val_str:
                    bal = Decimal(bal_str)
                    val = Decimal(val_str)
                    if bal > Decimal("0") and val > Decimal("0"):
                        price_pts = Decimal("100") * val / bal
                        isin_el = elem.find(".//isin")
                        isin = (
                            isin_el.attrib.get("value", "")
                            if isin_el is not None and "value" in isin_el.attrib
                            else (elem.findtext(".//isin") or "")
                        )
                        rt_str = elem.findtext(".//annualizedRt")
                        coupon_pct = Decimal(rt_str) if rt_str else None
                        mat_dt = (elem.findtext(".//maturityDt") or "").strip()
                        shelf = _manager_shelf(name)
                        shelf_par[shelf] += int(bal)
                        tranches.append({
                            "issuer": name,
                            "tranche": title,
                            "shelf": shelf,
                            "cusip": (elem.findtext("cusip") or "").strip(),
                            "isin": isin.strip(),
                            "par_usd_m": dec_round(bal / Decimal("1000000"), "0.02"),
                            "fair_val_usd_m": dec_round(val / Decimal("1000000"), "0.02"),
                            "clean_fair_price": dec_round(price_pts, "0.03"),
                            "coupon_pct": dec_round(coupon_pct, "0.02") if coupon_pct is not None else None,
                            "maturity": mat_dt,
                            "_bal": bal,
                            "_val": val,
                            "_price": price_pts,
                            "_coupon": coupon_pct,
                        })
            elem.clear()

    if not tranches:
        raise RuntimeError(f"Zero CLO tranches parsed from {symbol} ({accession})")

    tot_par = sum((t["_bal"] for t in tranches), Decimal("0"))
    tot_val = sum((t["_val"] for t in tranches), Decimal("0"))
    w_price = Decimal("100") * tot_val / tot_par

    coupon_par = sum((t["_bal"] for t in tranches if t["_coupon"] is not None), Decimal("0"))
    w_coupon = (
        sum((t["_bal"] * t["_coupon"] for t in tranches if t["_coupon"] is not None), Decimal("0")) / coupon_par
        if coupon_par > Decimal("0")
        else Decimal("0")
    )

    n_total = Decimal(len(tranches))
    below_99 = sum(1 for t in tranches if t["_price"] < Decimal("99.0"))
    below_98 = sum(1 for t in tranches if t["_price"] < Decimal("98.0"))

    by_par = sorted(tranches, key=lambda x: x["_bal"], reverse=True)[:4]
    by_discount = sorted(tranches, key=lambda x: x["_price"])[:3]
    seen_keys: set[tuple[str, str]] = set()
    sample: list[dict[str, Any]] = []
    for item in by_par + by_discount:
        k = (item["tranche"], item["isin"] or item["cusip"])
        if k in seen_keys:
            continue
        seen_keys.add(k)
        sample.append({key: val for key, val in item.items() if not key.startswith("_")})

    top_shelves = [
        {"shelf": sh, "par_usd_m": dec_round(Decimal(par_i) / Decimal("1000000"), "0.01")}
        for sh, par_i in shelf_par.most_common(5)
    ]

    return {
        "symbol": symbol,
        "series_name": series_name,
        "filing_date": filing_date,
        "report_period_date": rep_pd_date,
        "accession": accession,
        "archive_url": xml_url,
        "net_assets_usd_m": dec_round(net_assets / Decimal("1000000"), "0.01"),
        "clo_tranche_count": len(tranches),
        "clo_par_usd_m": dec_round(tot_par / Decimal("1000000"), "0.01"),
        "par_weighted_fair_price": dec_round(w_price, "0.03"),
        "par_weighted_coupon_pct": dec_round(w_coupon, "0.02"),
        "tranches_below_99_count": below_99,
        "tranches_below_99_pct": dec_round(Decimal("100") * Decimal(below_99) / n_total, "0.02"),
        "tranches_below_98_count": below_98,
        "min_tranche_price": min(t["clean_fair_price"] for t in tranches),
        "max_tranche_price": max(t["clean_fair_price"] for t in tranches),
        "top_manager_shelves": top_shelves,
        "representative_tranches": sample,
    }


def ingest_trustee_inbox(inbox_dir: Path = INBOX_TRUSTEE_DIR) -> list[dict[str, Any]]:
    """Normalize any operator-dropped European CLO trustee / CLO-i CSV or JSON extracts."""
    if not inbox_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for p in sorted(inbox_dir.iterdir()):
        if not p.is_file() or p.suffix.lower() not in (".csv", ".json"):
            continue
        digest = sha256_file(p)
        if p.suffix.lower() == ".json":
            raw = load_json(p)
            rows = raw if isinstance(raw, list) else raw.get("deals", [])
        else:
            with p.open("r", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        records.append({
            "filename": p.name,
            "sha256": digest,
            "deal_count": len(rows),
            "deals_preview": rows[:10],
        })
    return records


def sweep_clo_nport(stamp: str) -> dict[str, Any]:
    """Execute Gap G1 Form NPORT-P deal-level CLO sweep + trustee drop-in scan and seal JSON."""
    wl = load_watchlist()
    etf_summaries: list[dict[str, Any]] = []
    for trust in wl["clo_etf_trusts"]:
        found = _discover_latest_series_nports(trust["cik"], trust["series"])
        for s_name, sym in trust["series"].items():
            if s_name not in found:
                raise RuntimeError(f"Form NPORT-P series '{s_name}' not found in CIK {trust['cik']}")
            sym_code, f_date, acc = found[s_name]
            etf_summaries.append(_parse_nport_clo_series(trust["cik"], s_name, sym_code, f_date, acc))

    inbox_extracts = ingest_trustee_inbox()
    total_tranches = sum(e["clo_tranche_count"] for e in etf_summaries)
    by_sym = {e["symbol"]: e for e in etf_summaries}
    aaa_vs_mezz_price_diff = (
        dec_round(
            Decimal(str(by_sym["JAAA"]["par_weighted_fair_price"]))
            - Decimal(str(by_sym["JBBB"]["par_weighted_fair_price"])),
            "0.03",
        )
        if "JAAA" in by_sym and "JBBB" in by_sym
        else None
    )
    mezz_vs_aaa_coupon_pickup_bp = (
        dec_round(
            Decimal("100")
            * (
                Decimal(str(by_sym["JBBB"]["par_weighted_coupon_pct"]))
                - Decimal(str(by_sym["JAAA"]["par_weighted_coupon_pct"]))
            ),
            "0.1",
        )
        if "JAAA" in by_sym and "JBBB" in by_sym
        else None
    )

    payload: dict[str, Any] = {
        "schema": SCHEMA_CLO_TRANCHES,
        "date": stamp,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "sec_edgar_xbrl_nport",
        "summary": {
            "etf_series_ingested": len(etf_summaries),
            "total_deal_tranches_parsed": total_tranches,
            "aaa_vs_b_bbb_clean_price_diff_pts": aaa_vs_mezz_price_diff,
            "b_bbb_vs_aaa_coupon_pickup_bp": mezz_vs_aaa_coupon_pickup_bp,
            "european_trustee_inbox_files": len(inbox_extracts),
        },
        "etf_tranche_pools": etf_summaries,
        "european_trustee_inbox": inbox_extracts,
    }
    payload["sha256"] = seal_payload(payload)
    out_path = clo_tranches_path(stamp)
    save_json(out_path, payload)
    print(
        f"swept & sealed {total_tranches} deal-level CLO tranche(s) across {len(etf_summaries)} NPORT-P pool(s) in "
        f"{out_path.relative_to(ROOT).as_posix()} sha256={payload['sha256'][:16]}…"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    args = ap.parse_args(argv)
    sweep_clo_nport(args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

