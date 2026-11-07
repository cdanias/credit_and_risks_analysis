"""Deterministic Gap G2 sweeper: UK High Court Case Law XML, SEC EFTS restructuring filings & docket PDF sealer.

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (statutory court judgments & restructuring filings)
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
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    INBOX_DOCKETS_DIR,
    ROOT,
    SCHEMA_COURT_DOCKETS,
    SEC_USER_AGENT,
    court_dockets_path,
    load_watchlist,
    save_json,
    seal_payload,
    sha256_file,
)

UK_CASELAW_ATOM_URL = "https://caselaw.nationalarchives.gov.uk/atom.xml?query={query}"
SEC_EFTS_URL = "https://efts.sec.gov/LATEST/search-index?{params}"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom", "tna": "https://caselaw.nationalarchives.gov.uk"}
HTTP_TIMEOUT_SEC = 20


def _http_get_text(url: str, accept: str) -> str:
    """Fetch UTF-8 response body over HTTPS with explicit timeout and error chaining."""
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Docket request failed for {url}: {exc}") from exc


def fetch_uk_caselaw_judgments(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Query UK National Archives Find Case Law Atom/XML feed for High Court / appellate judgments."""
    seen_urls: set[str] = set()
    records: list[dict[str, Any]] = []
    for spec in queries:
        url = UK_CASELAW_ATOM_URL.format(query=urllib.parse.quote(str(spec["query"])))
        raw_xml = _http_get_text(url, accept="application/atom+xml,application/xml,text/xml")
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            raise RuntimeError(f"Malformed Atom XML from UK National Archives for {spec['query']}: {exc}") from exc
        count = 0
        limit = int(spec.get("limit", 5))
        for entry in root.findall("a:entry", ATOM_NS):
            if count >= limit:
                break
            link_el = entry.find("a:link", ATOM_NS)
            href = link_el.attrib.get("href", "") if link_el is not None else ""
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            # Extract court path segment from canonical URL (e.g. ewhc/ch/2026/2079)
            path_part = urllib.parse.urlparse(href).path.strip("/")
            records.append({
                "query_label": spec["label"],
                "case_title": (entry.findtext("a:title", "", ATOM_NS) or "").strip(),
                "court_path": path_part,
                "published_utc": (entry.findtext("a:published", "", ATOM_NS) or "").strip(),
                "updated_utc": (entry.findtext("a:updated", "", ATOM_NS) or "").strip(),
                "judgment_url": href,
                "akoma_ntoso_xml_url": f"{href}/data.xml",
            })
            count += 1
    return records


def fetch_sec_efts_restructuring_filings(
    queries: list[dict[str, Any]], as_of_stamp: str
) -> list[dict[str, Any]]:
    """Search SEC EDGAR EFTS full-text index for recent restructuring & credit filings."""
    end_dt = datetime.strptime(as_of_stamp, "%Y%m%d").date()
    start_dt = end_dt - timedelta(days=90)
    seen_ids: set[str] = set()
    records: list[dict[str, Any]] = []

    for spec in queries:
        params = urllib.parse.urlencode({
            "q": spec["query"],
            "forms": spec["forms"],
            "dateRange": "custom",
            "startdt": start_dt.isoformat(),
            "enddt": end_dt.isoformat(),
        })
        raw_json = _http_get_text(SEC_EFTS_URL.format(params=params), accept="application/json")
        try:
            doc = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed JSON from SEC EFTS for {spec['query']}: {exc}") from exc

        hits = doc.get("hits", {}).get("hits", [])
        limit = int(spec.get("limit", 4))
        count = 0
        for h in hits:
            if count >= limit:
                break
            doc_id = str(h.get("_id") or "")
            if not doc_id or doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            src = h.get("_source", {})
            ciks = src.get("ciks") or []
            cik_int = str(ciks[0]).lstrip("0") if ciks else ""
            if ":" in doc_id and cik_int:
                acc_part, file_part = doc_id.split(":", 1)
                archive_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_part.replace('-', '')}/{file_part}"
            else:
                acc_part, file_part, archive_url = doc_id, "", ""
            names = src.get("display_names") or []
            records.append({
                "query_label": spec["label"],
                "entity": names[0] if names else "SEC Filer",
                "form": src.get("form", ""),
                "file_date": src.get("file_date", ""),
                "accession": acc_part,
                "document": file_part,
                "archive_url": archive_url,
            })
            count += 1
    return records


def seal_local_docket_pdfs(inbox_dir: Path = INBOX_DOCKETS_DIR) -> list[dict[str, Any]]:
    """SHA-256-seal any locally dropped NYSCEF or High Court docket PDFs/texts."""
    if not inbox_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(inbox_dir.iterdir()):
        if not p.is_file():
            continue
        out.append({
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p),
        })
    return out


def sweep_court_dockets(stamp: str) -> dict[str, Any]:
    """Execute Gap G2 statutory UK Case Law + SEC EFTS + local docket sweep and seal JSON."""
    wl = load_watchlist()["docket_queries"]
    uk_judgments = fetch_uk_caselaw_judgments(wl["uk_caselaw_queries"])
    sec_filings = fetch_sec_efts_restructuring_filings(wl["sec_efts_queries"], stamp)
    local_pdfs = seal_local_docket_pdfs()

    payload: dict[str, Any] = {
        "schema": SCHEMA_COURT_DOCKETS,
        "date": stamp,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "uk_caselaw_and_efts_dockets",
        "summary": {
            "uk_judgments_count": len(uk_judgments),
            "sec_efts_filings_count": len(sec_filings),
            "local_sealed_dockets_count": len(local_pdfs),
        },
        "uk_high_court_judgments": uk_judgments,
        "sec_restructuring_filings": sec_filings,
        "local_docket_seals": local_pdfs,
    }
    payload["sha256"] = seal_payload(payload)
    out_path = court_dockets_path(stamp)
    save_json(out_path, payload)
    print(
        f"swept & sealed {len(uk_judgments)} UK court judgment(s) + {len(sec_filings)} SEC EFTS filing(s) in "
        f"{out_path.relative_to(ROOT).as_posix()} sha256={payload['sha256'][:16]}…"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    args = ap.parse_args(argv)
    sweep_court_dockets(args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

