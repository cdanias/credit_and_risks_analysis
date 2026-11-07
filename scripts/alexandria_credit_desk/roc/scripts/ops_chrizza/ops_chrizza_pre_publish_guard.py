"""Fail-closed pre-publish guard for Chrizza's structured credit dossier (v3).

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (operator intelligence publishing)
    Classifier    : CC-Bear · RC-Butterfly with roc/scripts/ops_thufir/ops_thufir_pre_publish_guard.py
    Lock status   : UNLOCKED — awaiting Agent Manager ratification

The guard turns each v1/v2 defect into a test that runs every cycle:
  * every figure has a declared provenance; sourced figures cite a sealed capture and are recent
  * prose may not contain bare quantities: numbers enter only through [[Fxx]] tokens
  * evidence seals must equal sha256(excerpt); FMP quote snapshots must pass payload seal check
  * every topic has five sections, at least three factors, and A/B/C scenarios summing to 100
  * every topic is current: NEW topics cite a dated news catalyst, RUNNING topics state today's delta
  * structured credit vectors (StructuredCreditSignalRecord) conform to domain bounds and cite sealed evidence
  * call conviction may not exceed the cap earned in the call ledger
  * the rendered HTML has no unfilled slots, no corrupted math, no compromised CDN, no self-applied lock
  * the canonical template and its runtime mirror are byte-identical

Usage:
    python ops_chrizza_pre_publish_guard.py --date YYYYMMDD [--html PATH]
Exit code 1 on any defect.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    ACTION_GATES,
    ALLOWED_TEX,
    CANONICAL_TEMPLATE,
    CONFIDENCE,
    DERIVED_OPS,
    JURISDICTIONS,
    LATEX_STATUS,
    MIRROR_TEMPLATE,
    NON_CLAIM_KEYS,
    ORIGINS,
    PROVENANCE,
    SCHEMA_BOND_ISINS,
    SCHEMA_CLO_TRANCHES,
    SCHEMA_CONTENT,
    SCHEMA_COURT_DOCKETS,
    SCHEMA_EVIDENCE,
    SCHEMA_NBFI_BDC,
    SCHEMA_QUOTES,
    TOKEN_RE,
    bond_isins_path,
    clo_tranches_path,
    content_path,
    court_dockets_path,
    evidence_path,
    load_json,
    load_registry,
    nbfi_bdc_path,
    parse_as_of,
    parse_utc,
    prior_content,
    quotes_path,
    seal_payload,
    sha256_file,
    sha256_text,
    thufir_content_path,
)
from ops_chrizza_learning_ledger import BAND_RANK, conviction_band, conviction_cap, load_ledger, stats  # noqa: E402

SOURCED_MAX_AGE_DAYS = 60
PULSE_VALUE_MAX_CHARS = 16
PULSE_LABEL_MAX_CHARS = 28
FIGURE_DISPLAY_MAX_CHARS = 34
SHORT_TITLE_MAX_CHARS = 28

# Topic freshness contract: topics are chosen from current news flow, never carried by habit.
FRESH_STATUS = ("new", "running")
CATALYST_TYPES = ("news", "telemetry")
# Windows are counted in business days (Mon–Fri) after the catalyst: structured credit is a niche,
# weekly-cadence market, so a NEW story stays new for one trading week (calibrated and ratified by the
# Agent Manager on 2026-11-07).
FRESH_NEW_MAX_DAYS = 5        # a NEW topic needs a news catalyst at most this many business days old
FRESH_RUNNING_MAX_DAYS = 10   # a RUNNING topic needs a catalyst (news or telemetry) at most this old
NEWS_CAPTURE_MARK = "search_web"  # capture_method marker of a news capture (vs sweeper telemetry)
FRESH_MIN_NEW_TOPICS = 1
FRESH_MIN_NATIVE_NEW_TOPICS = 1   # independence: at least one NEW topic must be found by Chrizza, not Thufir
# Editions observed before this date were published under the v3 contract and stay re-verifiable as-is.
FRESHNESS_EFFECTIVE = datetime(2026, 11, 7).date()

# Keys whose string values are prose shown to the reader: numbers must arrive via tokens.
PROSE_KEYS = {
    "headline", "verdict", "summary", "meaning", "extraction", "body", "ask", "why", "thesis",
    "why_now", "verify", "posture", "correction", "impact", "text", "event", "note", "rationale",
    "label", "sub", "title", "signal", "mechanism", "factors", "remedy", "used_for", "stance",
    "latex_note", "regime_label", "when", "stack_note", "macro_signal", "credit_channel", "delta",
}
# Subtrees and keys exempt from the bare-number scan (figure definitions, call specs, vectors, quoted priors, math).
SKIP_KEYS = {
    "figures", "credit_vectors", "prior", "kill_switch", "proposition",
    "value", "bounds", "display", "latex", "mermaid", "short_title",
}

BARE_NUMBER_RE = re.compile(
    r"[€£$]\s?\d|\d(?:[\d.,]*\d)?\s?(?:%|bps|bp|bn|billion|million|m|x|pts|p)(?![A-Za-z0-9])",
    re.IGNORECASE,
)
TOPIC_SECTIONS = ("signal", "mechanism", "factors", "scenarios", "posture")
TOPIC_REQUIRED = ("id", "emoji", "title", "thesis", "verdict", "stance", "risk", "evidence", "verify") + TOPIC_SECTIONS
CALL_REQUIRED = ("id", "topic", "proposition", "p", "resolve_by", "resolution_source")
VECTOR_REQUIRED = (
    "deal_or_loan_id", "topic", "market_jurisdiction", "ccc_bucket_percentage",
    "junior_oc_cushion_bp", "warf_score", "was_spread_bp", "lme_priming_risk_index",
    "default_intensity_forecast", "half_life_days", "action_gate", "evidence",
)

SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MATH_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
MERMAID_RE = re.compile(r'<div class="mermaid">.*?</div>', re.DOTALL)
CONTROL_RE = re.compile(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]")  # includes TAB: "\text" in a non-raw string
LEAK_RE = re.compile(r">\s*(None|nan|NaN|undefined|null)\s*<")
TEX_MACRO_RE = re.compile(r"\\([A-Za-z]+)")


def check_latex(where: str, latex: str) -> list[str]:
    """Structural pre-flight so MathJax never shows 'Math input error'."""
    defects: list[str] = []
    if CONTROL_RE.search(latex):
        defects.append(f"{where}: control character in formula (escape corruption)")
    depth = 0
    for ch in latex.replace("\\{", "").replace("\\}", ""):
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            break
    if depth != 0:
        defects.append(f"{where}: unbalanced braces in formula")
    macros = TEX_MACRO_RE.findall(latex)
    if macros.count("left") != macros.count("right"):
        defects.append(f"{where}: \\left and \\right are not paired")
    unknown = sorted(set(macros) - ALLOWED_TEX)
    if unknown:
        defects.append(f"{where}: TeX commands not on the allow-list {unknown}")
    if "$" in latex:
        defects.append(f"{where}: formula must not contain '$' delimiters")
    return defects


class _KeyGate(HTMLParser):
    """Collect visible text in <main> that is not inside a keyed element.

    Keyed = a figure span (class "fig"), a key badge (class "kbadge"), or any element carrying
    data-prov. Maths, Mermaid and SVG are drawn artefacts, keyed by their enclosing block.
    """

    VOID = {"br", "img", "meta", "link", "input", "hr", "source", "wbr", "col", "area", "base", "embed"}
    DRAWN = {"script", "style", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []  # (tag, keyed, inside <main>)
        self.unkeyed: list[str] = []
        self.bad_prov: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.VOID:
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        prov = a.get("data-prov")
        if prov is not None and prov not in PROVENANCE + NON_CLAIM_KEYS:
            self.bad_prov.add(prov)
        parent_keyed, parent_main = self.stack[-1][1:] if self.stack else (False, False)
        keyed = (parent_keyed or tag in self.DRAWN or prov is not None
                 or bool({"fig", "kbadge", "math", "mermaid"} & set(classes)))
        self.stack.append((tag, keyed, parent_main or tag == "main"))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1][2] and not self.stack[-1][1] and data.strip():
            self.unkeyed.append(data.strip())


def check_key_coverage(text: str) -> list[str]:
    """Every quantity rendered in <main> must sit inside a keyed element (the front-page key)."""
    gate = _KeyGate()
    gate.feed(text)
    defects = [f"html: data-prov '{p}' is not in the key {PROVENANCE + NON_CLAIM_KEYS}" for p in sorted(gate.bad_prov)]
    for chunk in gate.unkeyed:
        for m in BARE_NUMBER_RE.finditer(chunk):
            ctx = chunk[max(0, m.start() - 40): m.end() + 20]
            defects.append(f"html: unkeyed quantity '{m.group(0)}' in …{ctx}… — it matches none of the four keys")
    return defects


# ── Evidence & Quotes ─────────────────────────────────────────────────────
def check_evidence(evidence: dict[str, Any]) -> list[str]:
    """Schema, ID uniqueness and seal integrity of the evidence capture file."""
    defects: list[str] = []
    if evidence.get("schema") != SCHEMA_EVIDENCE:
        defects.append(f"evidence: schema must be {SCHEMA_EVIDENCE}")
    seen: set[str] = set()
    for item in evidence.get("items", []):
        eid = item.get("id", "?")
        if not re.fullmatch(r"E\d{2}", eid):
            defects.append(f"evidence {eid}: id must match E\\d\\d")
        if eid in seen:
            defects.append(f"evidence {eid}: duplicate id")
        seen.add(eid)
        for key in ("title", "capture_method", "query", "captured_at_utc", "publisher_domains", "excerpt"):
            if not item.get(key):
                defects.append(f"evidence {eid}: missing {key}")
        if item.get("excerpt") and item.get("sha256") != sha256_text(item["excerpt"]):
            defects.append(f"evidence {eid}: seal missing or does not match sha256(excerpt) — run `seal` at capture time")
        if "origin" in item and item["origin"] not in ORIGINS:
            defects.append(f"evidence {eid}: origin '{item['origin']}' not in {sorted(ORIGINS)}")
        if "native_after_exposure" in item:
            if not isinstance(item["native_after_exposure"], bool):
                defects.append(f"evidence {eid}: native_after_exposure must be a boolean")
            elif item["native_after_exposure"] and item.get("origin") != "chrizza_native":
                defects.append(f"evidence {eid}: native_after_exposure is only valid when origin is 'chrizza_native'")
    if not seen:
        defects.append("evidence: no items captured")
    return defects


def check_quotes(quotes: dict[str, Any]) -> list[str]:
    """Verify schema and cryptographic seal of an optional FMP credit proxy quotes snapshot."""
    defects: list[str] = []
    if quotes.get("schema") != SCHEMA_QUOTES:
        defects.append(f"quotes: schema must be {SCHEMA_QUOTES}")
    if quotes.get("sha256") != seal_payload(quotes):
        defects.append("quotes: payload sha256 seal mismatch — re-run `sweep-quotes`")
    if not quotes.get("quotes"):
        defects.append("quotes: no symbols captured in quotes dictionary")
    return defects


def check_nbfi_bdc(doc: dict[str, Any]) -> list[str]:
    """Verify schema, domain contents, and SHA-256 seal of Gap G4 (+ G3) FRED/EDGAR snapshot."""
    defects: list[str] = []
    if doc.get("schema") != SCHEMA_NBFI_BDC:
        defects.append(f"nbfi_bdc: schema must be {SCHEMA_NBFI_BDC}")
    if doc.get("sha256") != seal_payload(doc):
        defects.append("nbfi_bdc: payload sha256 seal mismatch — re-run `ops_chrizza_sweep_nbfi_and_bdc.py`")
    if not doc.get("fred_series"):
        defects.append("nbfi_bdc: missing fred_series observations")
    if not doc.get("bdc_records"):
        defects.append("nbfi_bdc: missing bdc_records XBRL analysis")
    return defects


def check_clo_tranches(doc: dict[str, Any]) -> list[str]:
    """Verify schema, tranche count, and SHA-256 seal of Gap G1 Form NPORT-P CLO snapshot."""
    defects: list[str] = []
    if doc.get("schema") != SCHEMA_CLO_TRANCHES:
        defects.append(f"clo_tranches: schema must be {SCHEMA_CLO_TRANCHES}")
    if doc.get("sha256") != seal_payload(doc):
        defects.append("clo_tranches: payload sha256 seal mismatch — re-run `ops_chrizza_sweep_clo_nport.py`")
    pools = doc.get("etf_tranche_pools") or []
    if not pools or int(doc.get("summary", {}).get("total_deal_tranches_parsed", 0)) <= 0:
        defects.append("clo_tranches: zero Form NPORT-P CLO tranches captured")
    return defects


def check_court_dockets(doc: dict[str, Any]) -> list[str]:
    """Verify schema, statutory hits, and SHA-256 seal of Gap G2 court & SEC EFTS dockets."""
    defects: list[str] = []
    if doc.get("schema") != SCHEMA_COURT_DOCKETS:
        defects.append(f"court_dockets: schema must be {SCHEMA_COURT_DOCKETS}")
    if doc.get("sha256") != seal_payload(doc):
        defects.append("court_dockets: payload sha256 seal mismatch — re-run `ops_chrizza_sweep_court_dockets.py`")
    if not doc.get("uk_high_court_judgments") and not doc.get("sec_restructuring_filings"):
        defects.append("court_dockets: neither UK High Court judgments nor SEC EFTS filings captured")
    return defects


def check_bond_isins(doc: dict[str, Any]) -> list[str]:
    """Verify schema, clean prices, and SHA-256 seal of Gap G5 Eurobond ISIN quotes."""
    defects: list[str] = []
    if doc.get("schema") != SCHEMA_BOND_ISINS:
        defects.append(f"bond_isins: schema must be {SCHEMA_BOND_ISINS}")
    if doc.get("sha256") != seal_payload(doc):
        defects.append("bond_isins: payload sha256 seal mismatch — re-run `ops_chrizza_sweep_bond_isins.py`")
    bonds = doc.get("bonds") or []
    if not bonds:
        defects.append("bond_isins: zero Eurobond ISINs captured")
    for b in bonds:
        if not b.get("isin") or not isinstance(b.get("mid"), (int, float)) or float(b["mid"]) <= 0:
            defects.append(f"bond_isins {b.get('isin', '?')}: invalid or non-positive mid clean price")
    return defects


def check_gap_feeds(stamp: str) -> list[str]:
    """Validate all present v4 Data Gap telemetry files for a session stamp."""
    defects: list[str] = []
    checks = (
        (nbfi_bdc_path(stamp), check_nbfi_bdc),
        (clo_tranches_path(stamp), check_clo_tranches),
        (court_dockets_path(stamp), check_court_dockets),
        (bond_isins_path(stamp), check_bond_isins),
    )
    for path, fn in checks:
        if path.exists():
            defects += fn(load_json(path))
    return defects


# ── Content ───────────────────────────────────────────────────────────────
def _scan_prose(node: Any, key: str | None, path: str, figures: dict, defects: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k not in SKIP_KEYS:
                _scan_prose(v, k, f"{path}.{k}", figures, defects)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _scan_prose(v, key, f"{path}[{i}]", figures, defects)
    elif isinstance(node, str):
        for token in TOKEN_RE.findall(node):
            if token not in figures:
                defects.append(f"{path}: token [[{token}]] does not resolve to a figure")
        stripped = TOKEN_RE.sub("", node)
        if "[[" in stripped or "]]" in stripped:
            defects.append(f"{path}: malformed figure token")
        if key in PROSE_KEYS:
            match = BARE_NUMBER_RE.search(stripped)
            if match:
                defects.append(f"{path}: bare quantity '{match.group(0)}' — register it as a figure and use a token")


def check_figures(figures: dict[str, Any], evidence_ids: set[str], observed: datetime) -> list[str]:
    """Every figure declares provenance; sourced figures cite sealed evidence and are recent."""
    defects: list[str] = []
    for fid, fig in figures.items():
        where = f"figure {fid}"
        if not re.fullmatch(r"F\d{2,3}", fid):
            defects.append(f"{where}: id must match F\\d{{2,3}}")
        for key in ("label", "display", "provenance", "confidence"):
            if not fig.get(key):
                defects.append(f"{where}: missing {key}")
        disp = str(fig.get("display") or "")
        if len(disp) > FIGURE_DISPLAY_MAX_CHARS:
            defects.append(
                f"{where}: display '{disp}' ({len(disp)} chars) exceeds {FIGURE_DISPLAY_MAX_CHARS}-char "
                "inline figure token limit (causes card/subtext overspill — move detail to label)"
            )
        prov = fig.get("provenance")
        if prov not in PROVENANCE:
            defects.append(f"{where}: provenance '{prov}' not in {PROVENANCE}")
        if fig.get("confidence") not in CONFIDENCE:
            defects.append(f"{where}: confidence must be one of {CONFIDENCE}")
        if prov == "sourced":
            if fig.get("evidence") not in evidence_ids:
                defects.append(f"{where}: sourced figure must cite a captured evidence id")
            if not fig.get("as_of"):
                defects.append(f"{where}: sourced figure needs as_of")
            else:
                try:
                    as_of = parse_as_of(fig["as_of"])
                except ValueError as exc:
                    defects.append(f"{where}: {exc}")
                else:
                    age = (observed.date() - as_of).days
                    if age < 0:
                        defects.append(f"{where}: as_of is after the observation time")
                    elif age > SOURCED_MAX_AGE_DAYS and not fig.get("historical"):
                        defects.append(f"{where}: as_of is {age} days old — mark historical or refresh")
        elif prov == "derived":
            inputs = fig.get("inputs") or []
            missing = [i for i in inputs if i not in figures]
            op = fig.get("op")
            val = fig.get("value")
            if not inputs or missing:
                defects.append(f"{where}: derived figure needs resolvable inputs (missing {missing})")
            elif op not in DERIVED_OPS:
                defects.append(f"{where}: derived figure op '{op}' must be one of {DERIVED_OPS}")
            elif not isinstance(val, (int, float)) or any(not isinstance(figures[i].get("value"), (int, float)) for i in inputs):
                defects.append(f"{where}: derived figure and all its inputs must have numeric values")
            else:
                vals = [float(figures[i]["value"]) for i in inputs]
                fval = float(val)
                if op == "diff" and (len(vals) != 2 or abs((vals[0] - vals[1]) - fval) > 1e-6):
                    defects.append(f"{where}: derived value does not equal {inputs[0]} − {inputs[1]}")
                elif op == "diff_bp" and (len(vals) != 2 or abs((vals[0] - vals[1]) * 100.0 - fval) > 0.5):
                    defects.append(f"{where}: derived diff_bp does not equal 100 × ({inputs[0]} − {inputs[1]})")
                elif op == "sum" and (len(vals) < 2 or abs(sum(vals) - fval) > 1e-6):
                    defects.append(f"{where}: derived sum does not equal sum({inputs})")
                elif op == "ratio_pct":
                    denom = sum(vals[1:])
                    if len(vals) < 2 or denom == 0 or abs((100.0 * vals[0] / denom) - fval) > 0.1:
                        defects.append(f"{where}: derived ratio_pct does not equal 100 × {inputs[0]} / sum({inputs[1:]})")
        elif prov in ("estimate", "illustrative") and not fig.get("rationale"):
            defects.append(f"{where}: {prov} figure needs a rationale")
    return defects


def check_topics(content: dict[str, Any], evidence_ids: set[str], gap_ids: set[str]) -> list[str]:
    """Five sections, evidence, factors, A/B/C scenarios summing to 100, kill switch on C."""
    defects: list[str] = []
    figures = content.get("figures", {})
    topics = content.get("topics", [])
    if not topics:
        defects.append("topics: none defined")
    for topic in topics:
        tid = topic.get("id", "?")
        for key in TOPIC_REQUIRED:
            if not topic.get(key):
                defects.append(f"topic {tid}: missing {key}")
        short_title = str(topic.get("short_title") or "").strip()
        full_title = str(topic.get("title") or "").strip()
        if short_title:
            if len(short_title) > SHORT_TITLE_MAX_CHARS:
                defects.append(
                    f"topic {tid}: short_title '{short_title}' ({len(short_title)} chars) exceeds "
                    f"{SHORT_TITLE_MAX_CHARS}-char tab button limit"
                )
        elif len(full_title) > SHORT_TITLE_MAX_CHARS:
            defects.append(
                f"topic {tid}: title ({len(full_title)} chars) exceeds {SHORT_TITLE_MAX_CHARS} chars without "
                f"an explicit short_title (<= {SHORT_TITLE_MAX_CHARS} chars), causing tab button truncation"
            )
        bad_ev = [e for e in topic.get("evidence", []) if e not in evidence_ids]
        if bad_ev:
            defects.append(f"topic {tid}: unknown evidence {bad_ev}")
        if len(topic.get("factors", [])) < 3:
            defects.append(f"topic {tid}: needs at least 3 factors")
        scenarios = topic.get("scenarios", [])
        if [s.get("id") for s in scenarios] != ["A", "B", "C"]:
            defects.append(f"topic {tid}: scenarios must be exactly A, B, C")
        probs = [s.get("p") for s in scenarios]
        if not all(isinstance(p, int) for p in probs) or sum(probs) != 100:
            defects.append(f"topic {tid}: scenario probabilities must be integers summing to 100 (got {probs})")
        if len(scenarios) == 3 and not scenarios[2].get("kill_switch"):
            defects.append(f"topic {tid}: scenario C needs a kill_switch")
        risk = topic.get("risk") or {}
        if not all(isinstance(risk.get(k), int) and 1 <= risk[k] <= 5 for k in ("probability", "impact")):
            defects.append(f"topic {tid}: risk probability and impact must be integers 1–5")
        bad_gaps = [g for g in topic.get("gaps", []) if g not in gap_ids]
        if bad_gaps:
            defects.append(f"topic {tid}: unknown gaps {bad_gaps}")
        if topic.get("latex"):
            defects += check_latex(f"topic {tid}", topic["latex"])
            if topic.get("latex_status") not in LATEX_STATUS:
                defects.append(f"topic {tid}: formula needs latex_status in {sorted(LATEX_STATUS)} — say honestly what it is")
            if not topic.get("latex_note"):
                defects.append(f"topic {tid}: formula needs a latex_note stating its limits")
        impure = [f for f in TOKEN_RE.findall(topic.get("signal", ""))
                  if figures.get(f, {}).get("provenance") not in ("sourced", "derived")]
        if impure:
            defects.append(f"topic {tid}: Signal is keyed 'sourced' but cites non-sourced figures {impure}")
        if topic.get("show_stack"):
            stack = figures.get(topic["show_stack"], {})
            shares = [s for _, s in stack.get("tranches", [])]
            if stack.get("provenance") != "illustrative" or abs(sum(shares) - 100) > 1e-9:
                defects.append(f"topic {tid}: show_stack must reference an illustrative figure whose tranches sum to 100")
            if not topic.get("stack_note"):
                defects.append(f"topic {tid}: show_stack needs a stack_note")
    return defects


def check_vectors(content: dict[str, Any], evidence_ids: set[str]) -> list[str]:
    """Validate optional StructuredCreditSignalRecord vectors emitted for alpha-g."""
    defects: list[str] = []
    vectors = content.get("credit_vectors")
    if not vectors:
        return defects
    topic_ids = {t.get("id") for t in content.get("topics", [])}
    seen: set[str] = set()
    for vec in vectors:
        vid = vec.get("deal_or_loan_id", "?")
        where = f"credit_vector {vid}"
        for key in VECTOR_REQUIRED:
            if vec.get(key) in (None, ""):
                defects.append(f"{where}: missing {key}")
        if vid in seen:
            defects.append(f"{where}: duplicate deal_or_loan_id")
        seen.add(vid)
        if vec.get("topic") not in topic_ids:
            defects.append(f"{where}: topic '{vec.get('topic')}' not in topics")
        if vec.get("market_jurisdiction") not in JURISDICTIONS:
            defects.append(f"{where}: market_jurisdiction must be one of {JURISDICTIONS}")
        if vec.get("action_gate") not in ACTION_GATES:
            defects.append(f"{where}: action_gate must be one of {ACTION_GATES}")
        if vec.get("evidence") not in evidence_ids:
            defects.append(f"{where}: evidence '{vec.get('evidence')}' not in captured evidence")
        lme = vec.get("lme_priming_risk_index")
        if not isinstance(lme, (int, float)) or not 0.0 <= float(lme) <= 1.0:
            defects.append(f"{where}: lme_priming_risk_index must be in [0.0, 1.0]")
        ccc = vec.get("ccc_bucket_percentage")
        if not isinstance(ccc, (int, float)) or not 0.0 <= float(ccc) <= 100.0:
            defects.append(f"{where}: ccc_bucket_percentage must be in [0.0, 100.0]")
        tau = vec.get("half_life_days")
        if not isinstance(tau, (int, float)) or float(tau) <= 0.0:
            defects.append(f"{where}: half_life_days must be > 0")
    return defects


def check_calls(content: dict[str, Any], ledger: dict[str, Any], observed: datetime) -> list[str]:
    """Calls are falsifiable, dated, not coin flips, and within the earned conviction cap."""
    defects: list[str] = []
    cap = conviction_cap(stats(ledger))
    topic_ids = {t.get("id") for t in content.get("topics", [])}
    seen: set[str] = set()
    calls = content.get("calls", [])
    if not calls:
        defects.append("calls: a dossier must publish at least one scoreable call")
    for call in calls:
        cid = call.get("id", "?")
        for key in CALL_REQUIRED:
            if call.get(key) in (None, ""):
                defects.append(f"call {cid}: missing {key}")
        if cid in seen:
            defects.append(f"call {cid}: duplicate id")
        seen.add(cid)
        if call.get("topic") not in topic_ids:
            defects.append(f"call {cid}: topic {call.get('topic')} not defined")
        p = call.get("p")
        if not isinstance(p, (int, float)) or not 0 < p < 1 or p == 0.5:
            defects.append(f"call {cid}: p must be in (0, 1) and not 0.5")
        elif BAND_RANK[conviction_band(p)] > BAND_RANK[cap]:
            defects.append(f"call {cid}: conviction '{conviction_band(p)}' exceeds ledger cap '{cap}'")
        try:
            if datetime.strptime(call.get("resolve_by", ""), "%Y-%m-%d").date() <= observed.date():
                defects.append(f"call {cid}: resolve_by must be after the observation date")
        except ValueError:
            defects.append(f"call {cid}: resolve_by must be YYYY-MM-DD")
    return defects


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def business_days_between(start: Any, end: Any) -> int:
    """Number of Mon–Fri days after `start` up to and including `end` (negative if end < start)."""
    if end < start:
        return -business_days_between(end, start)
    days, cur = 0, start
    while cur < end:
        cur += timedelta(days=1)
        days += cur.weekday() < 5
    return days


# Domain-generic structured-credit, agency and calendar terms that may appear in any credit search query.
GENERIC_QUERY_TOKENS = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "pik", "clo", "bdc", "lme", "sec", "edgar", "xbrl", "fred", "oas", "hy",
    "ig", "bsl", "wbs", "ytd", "sod", "eod", "eur", "usd", "gbp", "fitch", "moody", "moodys",
    "pitchbook", "lcd", "trepp", "creditflux", "octus", "9fin", "debtwire", "reuters", "bloomberg",
    "cnbc", "seekingalpha", "financial", "finance", "technology", "capital", "street", "main", "high",
    "court", "chapter", "first", "second", "third", "fourth", "quarter", "week", "term", "loan",
    "loans", "lien", "lenders", "private", "credit", "default", "rate", "rates", "spread", "spreads",
    "issuance", "resets", "bankruptcy", "filing", "files", "company", "published", "record", "tender",
    "offer", "redemption", "requests", "uptier", "dropdown", "ruling", "lawsuit", "takeover",
    "practice", "restructuring", "announcement",
}


def check_independence(evidence: dict[str, Any], thufir_doc: dict[str, Any] | None = None) -> list[str]:
    """Mechanical verification of 'chrizza_native' claims against Thufir-seeded leads and exposure timestamps."""
    defects: list[str] = []
    ev_items = evidence.get("items", [])
    if thufir_doc is None:
        m = re.search(r"(\d{8})$", str(evidence.get("dossier_id") or ""))
        if m and thufir_content_path(m.group(1)).exists():
            thufir_doc = load_json(thufir_content_path(m.group(1)))

    lead_tokens: set[str] = set()
    for item in ev_items:
        if item.get("origin") == "thufir_seeded":
            for tok in re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", str(item.get("query") or "")):
                if tok.lower() not in GENERIC_QUERY_TOKENS:
                    lead_tokens.add(tok.lower())
            for tk in re.findall(r"\$([A-Z]{2,5})\b", str(item.get("excerpt") or "")):
                if tk.lower() not in GENERIC_QUERY_TOKENS:
                    lead_tokens.add(tk.lower())
    if thufir_doc:
        for tk in re.findall(r"\$([A-Z]{2,5})\b", str(thufir_doc)):
            if tk.lower() not in GENERIC_QUERY_TOKENS:
                lead_tokens.add(tk.lower())

    exposure_timestamps: list[datetime] = []
    for item in ev_items:
        hay = f"{item.get('capture_method', '')} {item.get('query', '')}"
        if "ops_thufir" in hay or "dossier_content_" in hay:
            try:
                exposure_timestamps.append(parse_utc(str(item.get("captured_at_utc") or "")))
            except ValueError:
                pass
    exposure_ts = min(exposure_timestamps) if exposure_timestamps else None

    for item in ev_items:
        if item.get("origin") != "chrizza_native":
            continue
        eid = item.get("id", "?")
        q = str(item.get("query") or "")
        q_words = {w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9-]{2,}\b", q)}
        q_tickers = {t.lower() for t in re.findall(r"\$([A-Z]{2,5})\b", q)}
        leaked = sorted((q_words & lead_tokens) | q_tickers)
        if leaked:
            defects.append(
                f"independence: evidence {eid} is marked 'chrizza_native' but its query contains "
                f"Thufir-seeded lead token(s) {leaked} — mark origin 'thufir_seeded'"
            )
        if exposure_ts is not None:
            try:
                ts = parse_utc(str(item.get("captured_at_utc") or ""))
            except ValueError:
                continue
            if ts > exposure_ts and item.get("native_after_exposure") is not True:
                defects.append(
                    f"independence: evidence {eid} is marked 'chrizza_native' but was captured at "
                    f"{item.get('captured_at_utc')} after upstream Thufir exposure "
                    f"({exposure_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}) without 'native_after_exposure': true"
                )
    return defects


def check_freshness(content: dict[str, Any], evidence: dict[str, Any], observed: datetime,
                    prior: dict[str, Any] | None = None) -> list[str]:
    """Every topic must be justified by current flow: NEW = dated news catalyst, RUNNING = dated delta.

    Prevents a dossier from re-publishing yesterday's narrative (or a watch-list habit) as today's news.
    """
    defects: list[str] = []
    if observed.date() < FRESHNESS_EFFECTIVE:
        return defects
    items = {i.get("id"): i for i in evidence.get("items", [])}
    prior_topics = (prior or {}).get("topics", [])
    prior_titles = {_norm(t.get("title")) for t in prior_topics}
    prior_deltas = {_norm((t.get("freshness") or {}).get("delta")) for t in prior_topics} - {""}
    prior_threads = {(t.get("freshness") or {}).get("thread") for t in prior_topics} - {None, ""}
    seen_threads: set[str] = set()
    new_count = 0
    native_new = 0
    for topic in content.get("topics", []):
        tid = topic.get("id", "?")
        f = topic.get("freshness")
        where = f"topic {tid} freshness"
        if not isinstance(f, dict):
            defects.append(f"{where}: missing — every topic must declare status, catalyst and evidence")
            continue
        thread = str(f.get("thread") or "")
        if not re.fullmatch(r"[a-z0-9_]{3,48}", thread):
            defects.append(f"{where}: thread must be a stable snake_case story key (3–48 chars) carried day over day")
        elif thread in seen_threads:
            defects.append(f"{where}: thread '{thread}' is used by more than one topic")
        seen_threads.add(thread)
        status, ctype = f.get("status"), f.get("catalyst_type")
        if status not in FRESH_STATUS:
            defects.append(f"{where}: status must be one of {FRESH_STATUS}")
        if ctype not in CATALYST_TYPES:
            defects.append(f"{where}: catalyst_type must be one of {CATALYST_TYPES}")
        cat_ev = f.get("catalyst_evidence") or []
        if not cat_ev:
            defects.append(f"{where}: catalyst_evidence must cite at least one capture")
        unknown = [e for e in cat_ev if e not in items or e not in topic.get("evidence", [])]
        if unknown:
            defects.append(f"{where}: catalyst_evidence {unknown} must be captured and listed in the topic's evidence")
        dates: dict[str, Any] = {}
        for key in ("latest_catalyst", "first_reported"):
            try:
                dates[key] = datetime.strptime(str(f.get(key, "")), "%Y-%m-%d").date()
            except ValueError:
                defects.append(f"{where}: {key} must be YYYY-MM-DD")
        if len(dates) == 2:
            latest, first = dates["latest_catalyst"], dates["first_reported"]
            age = business_days_between(latest, observed.date())
            if latest > observed.date():
                defects.append(f"{where}: latest_catalyst is after the observation time")
            if first > latest:
                defects.append(f"{where}: first_reported is after latest_catalyst")
            limit = FRESH_NEW_MAX_DAYS if status == "new" else FRESH_RUNNING_MAX_DAYS
            if age > limit:
                defects.append(f"{where}: latest catalyst is {age} business days old (> {limit} for '{status}') — "
                               "the topic is stale; replace it with current news flow")
        if status == "new":
            new_count += 1
            if ctype != "news":
                defects.append(f"{where}: a NEW topic must be driven by a news catalyst, not telemetry alone")
            if not any(NEWS_CAPTURE_MARK in str(items.get(e, {}).get("capture_method", "")) for e in cat_ev):
                defects.append(f"{where}: a NEW topic must cite at least one news capture ({NEWS_CAPTURE_MARK})")
            if any(items.get(e, {}).get("origin") == "chrizza_native" for e in cat_ev):
                native_new += 1
            if _norm(topic.get("title")) in prior_titles:
                defects.append(f"{where}: title was already published in the prior dossier — mark it 'running'")
            if thread in prior_threads:
                defects.append(f"{where}: thread '{thread}' continues a prior-edition story — mark it 'running'")
        elif status == "running":
            delta = _norm(f.get("delta"))
            if not delta:
                defects.append(f"{where}: a RUNNING topic must state what is new today (delta)")
            elif delta in prior_deltas:
                defects.append(f"{where}: delta repeats the prior dossier verbatim — nothing new to report")
    if content.get("topics") and new_count < FRESH_MIN_NEW_TOPICS:
        defects.append(f"freshness: at least {FRESH_MIN_NEW_TOPICS} topic must be NEW (news-led) each edition")
    if content.get("topics") and native_new < FRESH_MIN_NATIVE_NEW_TOPICS:
        defects.append(f"independence: at least {FRESH_MIN_NATIVE_NEW_TOPICS} NEW topic must cite a 'chrizza_native' "
                       "catalyst — Chrizza's own domain search, not a Thufir-seeded lead")
    unlabelled = [i.get("id") for i in evidence.get("items", []) if i.get("origin") not in ORIGINS]
    if unlabelled:
        defects.append(f"independence: evidence {unlabelled} must declare origin in {sorted(ORIGINS)}")
    defects += check_independence(evidence)
    return defects


def check_content(content: dict[str, Any], evidence: dict[str, Any], registry: dict[str, dict],
                  ledger: dict[str, Any], prior: dict[str, Any] | None = None) -> list[str]:
    """All content-level checks (prior = previous edition, the freshness baseline)."""
    defects: list[str] = []
    if content.get("schema") != SCHEMA_CONTENT:
        defects.append(f"content: schema must be {SCHEMA_CONTENT}")
    try:
        observed = parse_utc(content.get("observed_at_utc", ""))
    except ValueError:
        return defects + ["content: observed_at_utc must be YYYY-MM-DDTHH:MM:SSZ"]

    figures = content.get("figures", {})
    evidence_ids = {i.get("id") for i in evidence.get("items", [])}
    gap_ids = {g.get("id") for g in content.get("gaps", [])}

    defects += check_figures(figures, evidence_ids, observed)
    _scan_prose(content, None, "content", figures, defects)
    defects += check_topics(content, evidence_ids, gap_ids)
    defects += check_freshness(content, evidence, observed, prior)
    defects += check_vectors(content, evidence_ids)
    defects += check_calls(content, ledger, observed)

    brief = content.get("brief", {})
    for key in ("regime_label", "regime_score_fig", "headline", "summary", "pulse", "decisions",
                "opportunities", "vetoes", "calendar", "mermaid"):
        if not brief.get(key):
            defects.append(f"brief: missing {key}")
    score_fig = figures.get(brief.get("regime_score_fig"), {})
    if not isinstance(score_fig.get("value"), (int, float)) or not -100 <= score_fig["value"] <= 100:
        defects.append("brief: regime_score_fig must reference a figure with a value in [-100, 100]")
    for card in brief.get("pulse", []):
        pfig_id = card.get("fig")
        plabel = str(card.get("label") or "")
        if len(plabel) > PULSE_LABEL_MAX_CHARS:
            defects.append(
                f"brief.pulse[{plabel}]: card title label ({len(plabel)} chars) exceeds "
                f"{PULSE_LABEL_MAX_CHARS}-char KPI card header limit (causes title overspill)"
            )
        if pfig_id not in figures:
            defects.append(f"brief.pulse: figure {pfig_id} not defined")
        else:
            pdisp = str(figures[pfig_id].get("display") or "")
            if len(pdisp) > PULSE_VALUE_MAX_CHARS or "(" in pdisp or ";" in pdisp:
                defects.append(
                    f"brief.pulse[{plabel}]: figure {pfig_id} display '{pdisp}' ({len(pdisp)} chars) "
                    f"exceeds {PULSE_VALUE_MAX_CHARS}-char KPI headline limit or contains parenthetical/semicolon "
                    "subtext (causes KPI card value overspill — keep display concise and move detail to pulse.sub)"
                )

    if "corrections" in content:
        defects.append("content: no corrections section — editions do not discuss earlier versions; "
                       "accountability is carried by the scored call ledger")

    for entry in content.get("bibliography", []):
        if entry.get("candidate"):
            if not entry.get("domain"):
                defects.append("bibliography: candidate source needs a domain")
        elif entry.get("source_id") not in registry:
            defects.append(f"bibliography: source_id '{entry.get('source_id')}' not in the registry")
    return defects


# ── Rendered HTML and template ────────────────────────────────────────────
def check_html(text: str) -> list[str]:
    """Integrity of the rendered dossier."""
    defects: list[str] = []
    body = COMMENT_RE.sub("", SCRIPT_STYLE_RE.sub("", text))
    visible = MERMAID_RE.sub("", MATH_RE.sub("", body))
    if "{{" in visible or "}}" in visible:
        defects.append("html: unfilled template slot")
    if "[[F" in text:
        defects.append("html: unresolved figure token")
    if "polyfill.io" in text.lower():
        defects.append("html: polyfill.io is banned (2024 supply-chain compromise)")
    if "\U0001F48E" in text:
        defects.append("html: lock glyph present — only the Agent Manager may ratify a lock")
    for i, block in enumerate(MATH_RE.findall(body)):
        if CONTROL_RE.search(block):
            defects.append(f"html: control character inside math block {i} (escape corruption)")
    for brand in ("infinix", "sgc"):
        if not re.search(rf'class="brand-logo {brand}"[^>]*>\s*<svg', text):
            defects.append(f"html: {brand} brand logo missing")
    sgc_at, meta_at = text.find('class="brand-logo sgc"'), text.find('class="meta-strip"')
    if sgc_at != -1 and meta_at != -1 and sgc_at < meta_at:
        defects.append("html: SGC logo must sit on the right, after the meta pills (house dossier format)")
    header = re.search(r'<header class="masthead">.*?</header>', text, re.DOTALL)
    if not header or '<nav class="tabs"' not in header.group(0):
        defects.append("html: tab bar must sit inside the sticky masthead so page links stay visible while scrolling")
    if "scrollbar-width: thin !important;" not in text or "::-webkit-scrollbar-thumb:hover" not in text:
        defects.append("html: missing house scrollbar CSS (Thufir dossier standard)")
    if ".kpi .kpi-value .fig" not in text or "overflow-wrap: break-word" not in text:
        defects.append("html: missing KPI card anti-overspill CSS (.kpi .kpi-value .fig / overflow-wrap: break-word)")
    leak = LEAK_RE.search(visible)
    if leak:
        defects.append(f"html: leaked null value '{leak.group(1)}'")
    heads = len(re.findall(r'class="sec-n"', text))
    keyed_heads = len(re.findall(r'class="sec-n">\d+</span><h3>[^<]*</h3><span class="kbadge kb-', text))
    if heads and keyed_heads < heads:
        defects.append(f"html: {heads - keyed_heads} topic section head(s) carry no key badge")
    defects += check_key_coverage(text)
    return defects


def check_template_sync() -> list[str]:
    """Canonical template and runtime mirror must be byte-identical."""
    if not CANONICAL_TEMPLATE.exists() or not MIRROR_TEMPLATE.exists():
        return ["template: canonical or mirror missing — run `sync-template`"]
    if sha256_file(CANONICAL_TEMPLATE) != sha256_file(MIRROR_TEMPLATE):
        return ["template: mirror has drifted from canonical — run `sync-template`"]
    return []


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Chrizza dossier pre-publish guard")
    parser.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    parser.add_argument("--html", help="rendered dossier to check")
    args = parser.parse_args(argv)

    evidence = load_json(evidence_path(args.date))
    defects = check_template_sync()
    defects += check_evidence(evidence)
    q_path = quotes_path(args.date)
    if q_path.exists():
        defects += check_quotes(load_json(q_path))
    defects += check_gap_feeds(args.date)
    defects += check_content(load_json(content_path(args.date)), evidence, load_registry(), load_ledger(),
                             prior_content(args.date))
    if args.html:
        defects += check_html(Path(args.html).read_text(encoding="utf-8"))

    for defect in defects:
        print(f"  ✗ {defect}")
    scope = "content + html" if args.html else "content"
    print(f"{'FAIL' if defects else 'PASS'} — {len(defects)} defect(s) [{scope}, {args.date}]")
    return 1 if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
