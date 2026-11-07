"""Tests for Chrizza's dossier pipeline: ledger maths, guard rules and an end-to-end render.

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (operator intelligence publishing)
    Classifier    : CC-Bear
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ops_chrizza_generate_credit_dossier as engine  # noqa: E402
import ops_chrizza_pre_publish_guard as guard  # noqa: E402
from ops_chrizza_dossier_common import (  # noqa: E402
    MIRROR_TEMPLATE,
    content_path,
    evidence_path,
    load_json,
    load_registry,
    sha256_text,
)
from ops_chrizza_learning_ledger import (  # noqa: E402
    conviction_band,
    conviction_cap,
    empty_ledger,
    register_calls,
    score_call,
    stats,
)

STAMP = "20261026"


@pytest.fixture()
def content() -> dict:
    return load_json(content_path(STAMP))


@pytest.fixture()
def evidence() -> dict:
    ev = load_json(evidence_path(STAMP))
    for item in ev["items"]:  # tests must not depend on whether `seal` has been run
        item["sha256"] = sha256_text(item["excerpt"])
    return ev


@pytest.fixture()
def registry() -> dict:
    return load_registry()


def _defects(content, evidence, registry, ledger=None) -> list[str]:
    return guard.check_content(content, evidence, registry, ledger or empty_ledger())


# ── Ledger ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("p, band", [(0.55, "low"), (0.40, "low"), (0.70, "medium"), (0.30, "medium"),
                                     (0.85, "high"), (0.10, "high")])
def test_conviction_band(p, band):
    assert conviction_band(p) == band


def test_cap_is_medium_until_ten_scored():
    assert conviction_cap(stats(empty_ledger())) == "medium"


def _scored_ledger(p: float, outcome: bool, n: int = 10) -> dict:
    ledger = empty_ledger()
    calls = [{"id": f"C-{i}", "topic": "T1", "proposition": "x", "p": p, "resolve_by": "2027-01-01",
              "resolution_source": "x"} for i in range(n)]
    register_calls(ledger, {"dossier_id": "D", "calls": calls}, "2026-01-01T00:00:00Z")
    for c in calls:
        score_call(ledger, c["id"], outcome, "evidence", "2027-01-02T00:00:00Z")
    return ledger


def test_cap_rises_with_a_good_record_and_falls_with_a_bad_one():
    good = stats(_scored_ledger(0.8, True))
    assert good["hit_rate"] == 1.0 and good["brier"] == pytest.approx(0.04)
    assert conviction_cap(good) == "high"
    bad = stats(_scored_ledger(0.8, False))
    assert conviction_cap(bad) == "low"


def test_register_is_idempotent_and_score_needs_evidence(content):
    ledger = empty_ledger()
    assert register_calls(ledger, content, "t") == len(content["calls"])
    assert register_calls(ledger, content, "t") == 0
    with pytest.raises(ValueError):
        score_call(ledger, content["calls"][0]["id"], True, "  ", "t")


# ── Guard: content ────────────────────────────────────────────────────────
def test_real_content_passes(content, evidence, registry):
    assert guard.check_evidence(evidence) == []
    assert _defects(content, evidence, registry) == []


def test_bare_number_in_prose_is_rejected(content, evidence, registry):
    content["brief"]["summary"] += " CCC buckets are at 6.2% today."
    assert any("bare quantity" in d for d in _defects(content, evidence, registry))


def test_unresolved_token_is_rejected(content, evidence, registry):
    content["brief"]["summary"] += " See [[F99]]."
    assert any("does not resolve" in d for d in _defects(content, evidence, registry))


def test_tampered_seal_is_rejected(evidence):
    evidence["items"][0]["excerpt"] += " edited"
    assert any("seal" in d for d in guard.check_evidence(evidence))


def test_scenarios_must_sum_to_100(content, evidence, registry):
    content["topics"][0]["scenarios"][0]["p"] += 5
    assert any("summing to 100" in d for d in _defects(content, evidence, registry))


def test_conviction_above_cap_is_rejected(content, evidence, registry):
    content["calls"][0]["p"] = 0.9
    assert any("exceeds ledger cap" in d for d in _defects(content, evidence, registry))


def test_stale_sourced_figure_is_rejected(content, evidence, registry):
    content["figures"]["F01"]["as_of"] = "2026-01-31"
    assert any("days old" in d for d in _defects(content, evidence, registry))


def test_corrupted_formula_is_rejected(content, evidence, registry):
    # Escape corruption: "\text" written in a non-raw Python string becomes TAB + "ext".
    content["topics"][0]["latex"] = "\text{Arb} = \frac{a}{b}"
    defects = _defects(content, evidence, registry)
    assert any("control character" in d for d in defects)


def test_unbalanced_or_unknown_tex_is_rejected():
    assert any("unbalanced" in d for d in guard.check_latex("t", r"\frac{a}{b"))
    assert any("paired" in d for d in guard.check_latex("t", r"\left( a"))
    assert any("allow-list" in d for d in guard.check_latex("t", r"\textbf{a}"))


def test_formula_without_honest_status_is_rejected(content, evidence, registry):
    del content["topics"][1]["latex_status"]
    assert any("latex_status" in d for d in _defects(content, evidence, registry))


def test_every_formula_in_content_is_clean(content):
    for topic in content["topics"]:
        if topic.get("latex"):
            assert guard.check_latex(topic["id"], topic["latex"]) == []


def test_signal_citing_an_estimate_is_rejected(content, evidence, registry):
    content["topics"][2]["signal"] += " SAR odds are [[F51]]."
    assert any("non-sourced figures" in d for d in _defects(content, evidence, registry))


def test_stack_must_be_an_illustrative_figure_summing_to_100(content, evidence, registry):
    content["figures"]["F60"]["tranches"][0][1] = 50.0
    assert any("show_stack" in d for d in _defects(content, evidence, registry))


def test_corrections_content_is_rejected(content, evidence, registry):
    content["corrections"] = [{"id": "K1", "prior": "x", "correction": "y"}]
    assert any("no corrections section" in d for d in _defects(content, evidence, registry))


def _render(content, evidence, registry) -> str:
    return engine.render_html(copy.deepcopy(content), evidence, empty_ledger(), registry,
                              MIRROR_TEMPLATE.read_text(encoding="utf-8"), [("x", "0" * 64)])


# ── Guard: HTML and end-to-end render ─────────────────────────────────────
def test_render_passes_html_guard(content, evidence, registry):
    html = _render(content, evidence, registry)
    assert guard.check_html(html) == []
    body = guard.SCRIPT_STYLE_RE.sub("", html)
    assert body.count("$$") == 2 * sum(1 for t in content["topics"] if t.get("latex"))
    assert "Stylised framework — not calibrated" in html
    assert "orrection" not in body  # first formal edition: no section about earlier versions
    assert "illustrative · 1" in html  # the capital stack is the one illustrative figure


@pytest.mark.parametrize("inject, expected", [
    ('<script src="https://polyfill.io/v3/polyfill.min.js"></script>', "polyfill"),
    ("<p>{{PIT_VAL}}</p>", "unfilled"),
    ("<div>$$\text{x}$$</div>", "control character"),
    ("<p>\U0001F48E</p>", "lock glyph"),
    ("<p>CCC buckets are at 6.2% today.</p>", "unkeyed quantity"),
    ('<p data-prov="rumour">x</p>', "not in the key"),
])
def test_html_guard_catches_publishing_defects(content, evidence, registry, inject, expected):
    html = _render(content, evidence, registry).replace("</main>", inject + "</main>")
    assert any(expected in d for d in guard.check_html(html))


def test_keyed_quantity_passes_the_key_gate(content, evidence, registry):
    html = _render(content, evidence, registry).replace(
        "</main>", '<p data-prov="estimate">CCC buckets near 6.2%.</p></main>')
    assert guard.check_key_coverage(html) == []


def test_sgc_logo_left_of_meta_pills_is_rejected(content, evidence, registry):
    html = _render(content, evidence, registry)
    logo = re.search(r'<span class="brand-logo sgc"[^>]*>.*?</svg>\s*</span>', html, re.DOTALL).group(0)
    moved = html.replace(logo, "", 1).replace('<div class="brand-title"', logo + '<div class="brand-title"', 1)
    assert any("SGC logo must sit on the right" in d for d in guard.check_html(moved))


def test_tab_bar_outside_sticky_masthead_is_rejected(content, evidence, registry):
    html = _render(content, evidence, registry)
    nav = re.search(r'\s*<nav class="tabs".*?</nav>', html, re.DOTALL).group(0)
    moved = html.replace(nav, "", 1).replace("<main>", nav + "\n<main>", 1)
    assert any("tab bar must sit inside the sticky masthead" in d for d in guard.check_html(moved))


def test_section_head_without_badge_is_rejected(content, evidence, registry):
    html = re.sub(r'(class="sec-n">1</span><h3>[^<]*</h3>)<span class="kbadge[^>]*>[^<]*</span>', r"\1",
                  _render(content, evidence, registry), count=1)
    assert any("carry no key badge" in d for d in guard.check_html(html))


# ── v3 Enhanced Pipeline: Quotes, Vectors, Thufir Bridge & 20261028 ───────
def test_20261028_dossier_passes_full_guard_and_renders(registry):
    from ops_chrizza_dossier_common import content_path, evidence_path, quotes_path, vectors_path, load_json
    c28 = load_json(content_path("20261028"))
    ev28 = load_json(evidence_path("20261028"))
    q28 = load_json(quotes_path("20261028"))
    assert guard.check_evidence(ev28) == []
    assert guard.check_quotes(q28) == []
    assert guard.check_content(c28, ev28, registry, empty_ledger()) == []
    html = engine.render_html(c28, ev28, empty_ledger(), registry,
                              MIRROR_TEMPLATE.read_text(encoding="utf-8"), [("x", "0" * 64)], q28)
    assert guard.check_html(html) == []
    assert "sim-cdr" in html and "updateWaterfallSim()" in html
    assert "Upstream Thufir Hawat Macro-to-Credit Transmission Bridge" in html
    assert "Liquid Structured Credit, Senior Loan &amp; BDC Proxy Tape" in html
    assert "fig-search-input" in html
    vpath = vectors_path("20261028")
    assert vpath.exists()
    vdoc = load_json(vpath)
    assert len(vdoc["records"]) == 6


def test_check_vectors_validates_bounds_and_enums():
    valid = [{
        "deal_or_loan_id": "TEST_CLO_1",
        "topic": "T1",
        "market_jurisdiction": "EUR_BSL",
        "ccc_bucket_percentage": 5.2,
        "junior_oc_cushion_bp": 410.0,
        "warf_score": 2800.0,
        "was_spread_bp": 355.0,
        "lme_priming_risk_index": 0.30,
        "equity_nav_mark": 58.0,
        "default_intensity_forecast": 0.04,
        "half_life_days": 45.0,
        "action_gate": "ALLOW",
        "evidence": "E01",
        "rationale": "Clean reinvesting shelf.",
    }]
    doc = {"credit_vectors": valid, "topics": [{"id": "T1"}]}
    assert guard.check_vectors(doc, {"E01"}) == []
    bad = copy.deepcopy(doc)
    bad["credit_vectors"][0]["action_gate"] = "INVALID_GATE"
    bad["credit_vectors"][0]["lme_priming_risk_index"] = 1.5
    defects = guard.check_vectors(bad, {"E01"})
    assert any("action_gate" in d for d in defects)
    assert any("lme_priming_risk_index" in d for d in defects)


def test_check_quotes_validates_seal():
    from ops_chrizza_dossier_common import quotes_path, load_json
    q28 = load_json(quotes_path("20261028"))
    assert guard.check_quotes(q28) == []
    tampered = copy.deepcopy(q28)
    tampered["quotes"]["JAAA"]["price"] = 99.99
    assert any("sha256" in d for d in guard.check_quotes(tampered))


def test_house_scrollbar_css_is_enforced_by_guard(content, evidence, registry):
    html = _render(content, evidence, registry)
    assert "scrollbar-width: thin !important;" in html
    assert "::-webkit-scrollbar-thumb:hover" in html
    assert "#06b6d4 !important" in html
    stripped = html.replace("scrollbar-width: thin !important;", "")
    assert any("missing house scrollbar CSS" in d for d in guard.check_html(stripped))


def test_20261029_dossier_passes_full_guard_and_renders(registry):
    from ops_chrizza_dossier_common import content_path, evidence_path, quotes_path, vectors_path, load_json
    c29 = load_json(content_path("20261029"))
    ev29 = load_json(evidence_path("20261029"))
    q29 = load_json(quotes_path("20261029"))
    gaps29 = engine.load_gap_feeds("20261029")
    assert guard.check_evidence(ev29) == []
    assert guard.check_quotes(q29) == []
    assert guard.check_gap_feeds("20261029") == []
    assert guard.check_content(c29, ev29, registry, empty_ledger()) == []
    html = engine.render_html(c29, ev29, empty_ledger(), registry,
                              MIRROR_TEMPLATE.read_text(encoding="utf-8"), [("x", "0" * 64)], q29, gaps29)
    assert guard.check_html(html) == []
    assert "Upstream Thufir Hawat Macro-to-Credit Transmission Bridge" in html
    assert "Liquid Structured Credit, Senior Loan &amp; BDC Proxy Tape" in html
    assert "Benchmark Eurobond &amp; UK WBS ISIN Order-Book Tape" in html
    assert "Statutory Fed H.8 Bank-to-NDFI Lending, Credit OAS &amp; SEC EDGAR BDC XBRL PIK Monitor" in html
    assert "SEC EDGAR Form NPORT-P Deal-Level CLO Tranche Telemetry" in html
    assert "Statutory UK High Court Case Law XML &amp; SEC EFTS Restructuring Filings" in html
    assert "HAWKISH-HOLD BEAR-STEEPENER" in html
    vpath = vectors_path("20261029")
    assert vpath.exists()
    vdoc = load_json(vpath)
    assert len(vdoc["records"]) == 6


# ── v4 Data Gap Registry Sweepers & Guard Validators ───────────────────────
def test_v4_check_nbfi_bdc_validates_seal_and_domain():
    from ops_chrizza_dossier_common import nbfi_bdc_path, load_json, seal_payload
    doc = load_json(nbfi_bdc_path("20261029"))
    assert guard.check_nbfi_bdc(doc) == []
    assert doc["fred_series"]["LNFACBW027SBOG"]["value"] > 2000.0
    tampered = copy.deepcopy(doc)
    tampered["fred_series"]["LNFACBW027SBOG"]["value"] = 0.0
    assert any("sha256" in d for d in guard.check_nbfi_bdc(tampered))
    empty_bdc = copy.deepcopy(doc)
    empty_bdc["bdc_records"] = []
    empty_bdc["sha256"] = seal_payload(empty_bdc)
    assert any("missing bdc_records" in d for d in guard.check_nbfi_bdc(empty_bdc))


def test_v4_check_bond_isins_validates_seal_and_positive_clean_mid():
    from ops_chrizza_dossier_common import bond_isins_path, load_json, seal_payload
    doc = load_json(bond_isins_path("20261029"))
    assert guard.check_bond_isins(doc) == []
    assert len(doc["bonds"]) == 12
    tampered = copy.deepcopy(doc)
    tampered["bonds"][0]["mid"] = 99.0
    assert any("sha256" in d for d in guard.check_bond_isins(tampered))
    neg = copy.deepcopy(doc)
    neg["bonds"][0]["mid"] = -5.0
    neg["sha256"] = seal_payload(neg)
    assert any("non-positive mid" in d for d in guard.check_bond_isins(neg))


def test_v4_check_clo_tranches_validates_seal_and_tranche_counts():
    from ops_chrizza_dossier_common import clo_tranches_path, load_json, seal_payload
    doc = load_json(clo_tranches_path("20261029"))
    assert guard.check_clo_tranches(doc) == []
    assert doc["summary"]["total_deal_tranches_parsed"] >= 800
    tampered = copy.deepcopy(doc)
    tampered["summary"]["total_deal_tranches_parsed"] = 999999
    assert any("sha256" in d for d in guard.check_clo_tranches(tampered))
    zero_doc = copy.deepcopy(doc)
    zero_doc["summary"]["total_deal_tranches_parsed"] = 0
    zero_doc["sha256"] = seal_payload(zero_doc)
    assert any("zero Form NPORT-P CLO tranches" in d for d in guard.check_clo_tranches(zero_doc))


def test_v4_check_court_dockets_validates_seal_and_statutory_hits():
    from ops_chrizza_dossier_common import court_dockets_path, load_json, seal_payload
    doc = load_json(court_dockets_path("20261029"))
    assert guard.check_court_dockets(doc) == []
    assert doc["summary"]["uk_judgments_count"] >= 1
    assert doc["summary"]["sec_efts_filings_count"] >= 1
    tampered = copy.deepcopy(doc)
    tampered["summary"]["uk_judgments_count"] = 0
    assert any("sha256" in d for d in guard.check_court_dockets(tampered))
    empty = copy.deepcopy(doc)
    empty["uk_high_court_judgments"] = []
    empty["sec_restructuring_filings"] = []
    empty["sha256"] = seal_payload(empty)
    assert any("neither UK High Court judgments nor SEC EFTS" in d for d in guard.check_court_dockets(empty))


def test_v4_ingest_trustee_inbox_normalizes_csv_and_json(tmp_path):
    from ops_chrizza_sweep_clo_nport import ingest_trustee_inbox
    csv_file = tmp_path / "eur_clo_trustee_sample.csv"
    csv_file.write_text(
        "deal,manager,was_bps,jr_oc_cushion_bp,ccc_pct\n"
        "Ares Euro CLO XVII,Ares,358,415,4.2\n"
        "CVC Cordatus XXX,CVC,342,185,6.8\n",
        encoding="utf-8",
    )
    json_file = tmp_path / "cloi_extract.json"
    json_file.write_text('{"deals": [{"deal": "Palmer Square EUR CLO 2025-1", "was_bps": 364}]}', encoding="utf-8")
    records = ingest_trustee_inbox(tmp_path)
    assert len(records) == 2
    by_name = {r["filename"]: r for r in records}
    assert by_name["eur_clo_trustee_sample.csv"]["deal_count"] == 2
    assert len(by_name["eur_clo_trustee_sample.csv"]["sha256"]) == 64
    assert by_name["cloi_extract.json"]["deal_count"] == 1


def test_v4_seal_local_docket_pdfs_hashes_files(tmp_path):
    from ops_chrizza_sweep_court_dockets import seal_local_docket_pdfs
    pdf = tmp_path / "nyscef_altice_complaint_20261013.pdf"
    pdf.write_bytes(b"%PDF-1.7 synthetic docket test bytes")
    sealed = seal_local_docket_pdfs(tmp_path)
    assert len(sealed) == 1
    assert sealed[0]["filename"] == "nyscef_altice_complaint_20261013.pdf"
    assert sealed[0]["size_bytes"] == len(b"%PDF-1.7 synthetic docket test bytes")
    assert len(sealed[0]["sha256"]) == 64


def test_20261031_weekend_dossier_passes_full_guard_and_renders():
    from ops_chrizza_dossier_common import (
        OUTPUT_DIR,
        content_path,
        evidence_path,
        load_json,
        load_registry,
        quotes_path,
        vectors_path,
    )
    from ops_chrizza_learning_ledger import load_ledger
    from ops_chrizza_pre_publish_guard import (
        check_content,
        check_evidence,
        check_gap_feeds,
        check_html,
        check_quotes,
        check_template_sync,
    )

    stamp = "20261031"
    ev = load_json(evidence_path(stamp))
    ct = load_json(content_path(stamp))
    qt = load_json(quotes_path(stamp))
    vecs = load_json(vectors_path(stamp))
    html_file = OUTPUT_DIR / f"Ops_Structured_Credit_CLO_Horizon_Dossier_{stamp}.html"

    assert check_template_sync() == []
    assert check_evidence(ev) == []
    assert check_quotes(qt) == []
    assert check_gap_feeds(stamp) == []
    assert check_content(ct, ev, load_registry(), load_ledger()) == []
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert check_html(html_text) == []
    assert "ARINI MARGIN FLUSH" in html_text
    assert len(vecs.get("records", [])) == 6


def test_20261106_sod_dossier_passes_full_guard_and_renders():
    from ops_chrizza_dossier_common import (
        OUTPUT_DIR,
        content_path,
        evidence_path,
        load_json,
        load_registry,
        quotes_path,
        vectors_path,
    )
    from ops_chrizza_learning_ledger import load_ledger
    from ops_chrizza_pre_publish_guard import (
        check_content,
        check_evidence,
        check_gap_feeds,
        check_html,
        check_quotes,
        check_template_sync,
    )

    stamp = "20261106"
    ev = load_json(evidence_path(stamp))
    ct = load_json(content_path(stamp))
    qt = load_json(quotes_path(stamp))
    vecs = load_json(vectors_path(stamp))
    html_file = OUTPUT_DIR / f"Ops_Structured_Credit_CLO_Horizon_Dossier_{stamp}.html"

    assert check_template_sync() == []
    assert check_evidence(ev) == []
    assert check_quotes(qt) == []
    assert check_gap_feeds(stamp) == []
    assert check_content(ct, ev, load_registry(), load_ledger()) == []
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert check_html(html_text) == []
    assert "AI PROJECT LOAN AUCTION" in html_text
    assert len(vecs.get("records", [])) == 6


# ── Card & Tab Title Anti-Overspill Verifications ─────────────────────────
def test_pulse_card_value_or_label_overspill_is_rejected(content, evidence, registry):
    bad_val = copy.deepcopy(content)
    pfig = bad_val["brief"]["pulse"][0]["fig"]
    bad_val["figures"][pfig]["display"] = "3.51% OAS (+19 bps; 8.19% yield)"
    defects = _defects(bad_val, evidence, registry)
    assert any("KPI headline limit" in d for d in defects)

    bad_lbl = copy.deepcopy(content)
    bad_lbl["brief"]["pulse"][0]["label"] = "EXTREMELY LONG KPI CARD TITLE LABEL OVER 28 CHARS"
    defects_lbl = _defects(bad_lbl, evidence, registry)
    assert any("KPI card header limit" in d for d in defects_lbl)


def test_figure_display_token_overspill_is_rejected(content, evidence, registry):
    bad = copy.deepcopy(content)
    bad["figures"]["F01"]["display"] = "49.03 mid (48.55–48.97 bids across all 4 ISINs)"
    assert any("inline figure token limit" in d for d in _defects(bad, evidence, registry))


def test_topic_missing_short_title_with_long_title_is_rejected(content, evidence, registry):
    bad_missing = copy.deepcopy(content)
    del bad_missing["topics"][0]["short_title"]
    assert any("causing tab button truncation" in d for d in _defects(bad_missing, evidence, registry))

    bad_long = copy.deepcopy(content)
    bad_long["topics"][0]["short_title"] = "This short title is over twenty-eight characters"
    assert any("tab button limit" in d for d in _defects(bad_long, evidence, registry))


def test_html_guard_enforces_kpi_card_anti_overspill_css(content, evidence, registry):
    html = _render(content, evidence, registry)
    assert ".kpi .kpi-value .fig" in html
    stripped = html.replace(".kpi .kpi-value .fig", ".kpi .kpi-value .removed")
    assert any("missing KPI card anti-overspill CSS" in d for d in guard.check_html(stripped))


# ── Topic freshness contract (v5) ─────────────────────────────────────────
from datetime import datetime as _dt  # noqa: E402

_OBS = _dt(2026, 11, 7, 10, 0, 0)
_EV = {"items": [
    {"id": "E01", "capture_method": "search_web grounded summary", "origin": "chrizza_native"},
    {"id": "E02", "capture_method": "ops_chrizza_sweep_bond_isins.py live exchange capture", "origin": "telemetry"},
    {"id": "E03", "capture_method": "search_web on a Thufir lead", "origin": "thufir_seeded"},
]}


def _topic(tid: str, title: str, **fresh) -> dict:
    base = {"thread": f"story_{tid.lower()}", "status": "new", "catalyst_type": "news", "first_reported": "2026-11-06",
            "latest_catalyst": "2026-11-06", "catalyst_evidence": ["E01"], "delta": ""}
    base.update(fresh)
    return {"id": tid, "title": title, "evidence": ["E01", "E02"], "freshness": base}


def test_fresh_news_led_topics_pass():
    doc = {"topics": [_topic("T1", "AI lease walk-aways"),
                      _topic("T2", "Old water story", status="running", catalyst_type="telemetry",
                             first_reported="2026-10-16", latest_catalyst="2026-11-07",
                             catalyst_evidence=["E02"], delta="Two notes slipped below half of par.")]}
    assert guard.check_freshness(doc, _EV, _OBS) == []


def test_new_topic_needs_recent_news_catalyst():
    stale = {"topics": [_topic("T1", "Stale", latest_catalyst="2026-10-28", first_reported="2026-10-28")]}
    assert any("days old" in d for d in guard.check_freshness(stale, _EV, _OBS))
    telemetry_only = {"topics": [_topic("T1", "Tape only", catalyst_type="telemetry", catalyst_evidence=["E02"])]}
    defects = guard.check_freshness(telemetry_only, _EV, _OBS)
    assert any("news catalyst" in d for d in defects) and any("news capture" in d for d in defects)


def test_running_topic_needs_a_fresh_delta_and_new_topic_cannot_repeat_title():
    prior = {"topics": [{"title": "Thames saga", "freshness": {"delta": "Same words."}}]}
    doc = {"topics": [_topic("T1", "Thames saga"),
                      _topic("T2", "Running", status="running", delta="Same words.")]}
    defects = guard.check_freshness(doc, _EV, _OBS, prior)
    assert any("already published" in d for d in defects)
    assert any("repeats the prior dossier" in d for d in defects)
    no_delta = {"topics": [_topic("T1", "A"), _topic("T2", "B", status="running")]}
    assert any("what is new today" in d for d in guard.check_freshness(no_delta, _EV, _OBS))


def test_edition_needs_at_least_one_new_topic_and_missing_block_fails():
    only_running = {"topics": [_topic("T1", "R", status="running", delta="Moved.")]}
    assert any("must be NEW" in d for d in guard.check_freshness(only_running, _EV, _OBS))
    assert any("missing" in d for d in guard.check_freshness({"topics": [{"id": "T1"}]}, _EV, _OBS))


def test_legacy_editions_are_grandfathered():
    assert guard.check_freshness({"topics": [{"id": "T1"}]}, _EV, _dt(2026, 11, 6)) == []


def test_business_days_skip_weekends():
    from datetime import date
    assert guard.business_days_between(date(2026, 11, 2), date(2026, 11, 7)) == 4   # Mon -> Sat
    assert guard.business_days_between(date(2026, 10, 30), date(2026, 11, 2)) == 1  # Fri -> Mon


def test_independence_requires_a_native_new_topic_and_labelled_evidence():
    thufir_only = {"topics": [_topic("T1", "Echo", catalyst_evidence=["E03"]),
                              _topic("T2", "Echo two", catalyst_evidence=["E03"])]}
    ev = {"items": _EV["items"] + []}
    doc_ev = copy.deepcopy(ev)
    for t in thufir_only["topics"]:
        t["evidence"] = ["E01", "E02", "E03"]
    assert any("chrizza_native" in d for d in guard.check_freshness(thufir_only, doc_ev, _OBS))
    unlabelled = copy.deepcopy(_EV)
    del unlabelled["items"][1]["origin"]
    assert any("must declare origin" in d
               for d in guard.check_freshness({"topics": [_topic("T1", "A")]}, unlabelled, _OBS))
    bad = {"schema": "chrizza.evidence.v1", "items": [
        {"id": "E01", "title": "t", "capture_method": "m", "query": "q", "captured_at_utc": "x",
         "publisher_domains": ["d"], "excerpt": "e", "sha256": sha256_text("e"), "origin": "rumour"}]}
    assert any("origin 'rumour'" in d for d in guard.check_evidence(bad))


def test_threads_are_required_unique_and_new_cannot_continue_a_prior_thread():
    bad = {"topics": [_topic("T1", "A", thread="Bad Key"), _topic("T2", "B", thread="dup_key"),
                      _topic("T3", "C", thread="dup_key")]}
    defects = guard.check_freshness(bad, _EV, _OBS)
    assert any("snake_case story key" in d for d in defects)
    assert any("more than one topic" in d for d in defects)
    prior = {"topics": [{"title": "Old", "freshness": {"thread": "story_t1", "delta": "x"}}]}
    assert any("continues a prior-edition story" in d
               for d in guard.check_freshness({"topics": [_topic("T1", "Renamed story")]}, _EV, _OBS, prior))


def test_freshness_board_lists_today_and_retired_threads():
    c = {"topics": [_topic("T1", "Fresh story"),
                    _topic("T2", "Carried", status="running", delta="Moved.", thread="kept_story")]}
    prior = {"dossier_id": "CHZ-PRIOR", "topics": [
        {"title": "Kept", "freshness": {"thread": "kept_story"}},
        {"title": "Gone quiet", "freshness": {"thread": "old_story"}}]}
    html = engine.freshness_board_html(c, prior, _EV)
    assert "🆕 NEW" in html and "♻️ RUNNING" in html
    assert "Gone quiet" in html and ">Kept<" not in html and "retired" in html
    assert "Chrizza-native" in html and "Evidence independence" in html


def test_bond_tape_links_only_themes_claimed_by_current_topics():
    from ops_chrizza_dossier_common import bond_isins_path, load_json
    doc = load_json(bond_isins_path("20261107"))
    unclaimed = engine.bond_isins_html(doc, [{"id": "T1"}])
    assert "tag-jump" not in unclaimed and "watch-list" in unclaimed
    assert "Thames Water Class A Avg Mid" not in unclaimed
    claimed = engine.bond_isins_html(doc, [{"id": "T5", "watch_themes": ["thames_water_wbs"]}])
    assert "switchTab('tab-5')" in claimed and claimed.count("switchTab('tab-5')") == 4


def test_derived_figures_validate_all_supported_ops_and_reject_unknown_or_bad_math():
    obs = _dt(2026, 11, 7, 10, 0, 0)
    figs = {
        "F01": {"label": "A", "display": "122.5", "value": 122.5, "provenance": "sourced", "confidence": "high", "as_of": "2026-11-02", "evidence": "E01"},
        "F02": {"label": "B", "display": "6.5", "value": 6.5, "provenance": "sourced", "confidence": "high", "as_of": "2026-11-02", "evidence": "E01"},
        "F03": {"label": "Bid", "display": "26.3", "value": 26.3, "provenance": "sourced", "confidence": "high", "as_of": "2026-11-02", "evidence": "E01"},
        "F04": {"label": "Diff", "display": "116.0", "value": 116.0, "provenance": "derived", "confidence": "high", "inputs": ["F01", "F02"], "op": "diff"},
        "F05": {"label": "Sum", "display": "129.0", "value": 129.0, "provenance": "derived", "confidence": "high", "inputs": ["F01", "F02"], "op": "sum"},
        "F06": {"label": "RatioPct", "display": "20.4%", "value": 20.4, "provenance": "derived", "confidence": "high", "inputs": ["F03", "F01", "F02"], "op": "ratio_pct"},
        "F07": {"label": "DiffBp", "display": "11600 bp", "value": 11600.0, "provenance": "derived", "confidence": "high", "inputs": ["F01", "F02"], "op": "diff_bp"},
    }
    assert guard.check_figures(figs, {"E01"}, obs) == []

    bad_op = copy.deepcopy(figs)
    bad_op["F06"]["op"] = "ratio"
    assert any("must be one of" in d for d in guard.check_figures(bad_op, {"E01"}, obs))

    bad_ratio = copy.deepcopy(figs)
    bad_ratio["F06"]["value"] = 35.0
    assert any("derived ratio_pct" in d for d in guard.check_figures(bad_ratio, {"E01"}, obs))

    bad_sum = copy.deepcopy(figs)
    bad_sum["F05"]["value"] = 200.0
    assert any("derived sum" in d for d in guard.check_figures(bad_sum, {"E01"}, obs))


def test_check_independence_rejects_thufir_lead_tokens_and_unmarked_post_exposure_captures():
    ev = {
        "dossier_id": "CHZ-CREDIT-20261107",
        "items": [
            {
                "id": "E01",
                "origin": "thufir_seeded",
                "captured_at_utc": "2026-11-07T10:19:15Z",
                "capture_method": "local file read of roc/scripts/ops_thufir/content/dossier_content_20261107.json",
                "query": "Signifyd Crusoe Oracle THUFIR-20261107-SOD",
                "excerpt": "Upstream $OTF and $ORCL.",
            },
            {
                "id": "E02",
                "origin": "chrizza_native",
                "captured_at_utc": "2026-11-07T10:18:00Z",
                "capture_method": "search_web",
                "query": "Chapter 11 bankruptcy filing first lien lenders week November 6 2026",
                "excerpt": "Pre-exposure open query.",
            },
        ],
    }
    assert guard.check_independence(ev, thufir_doc={}) == []

    leaked_query = copy.deepcopy(ev)
    leaked_query["items"][1]["query"] = "Signifyd 11% PIK non-accrual lenders"
    assert any("Thufir-seeded lead token(s) ['signifyd']" in d for d in guard.check_independence(leaked_query, thufir_doc={}))

    post_unmarked = copy.deepcopy(ev)
    post_unmarked["items"][1]["captured_at_utc"] = "2026-11-07T12:16:00Z"
    assert any("without 'native_after_exposure': true" in d for d in guard.check_independence(post_unmarked, thufir_doc={}))

    post_marked = copy.deepcopy(post_unmarked)
    post_marked["items"][1]["native_after_exposure"] = True
    assert guard.check_independence(post_marked, thufir_doc={}) == []


def test_content_builder_split_check_chunk_and_assemble_round_trip(tmp_path):
    import ops_chrizza_content_builder as builder
    from ops_chrizza_dossier_common import content_path, load_json

    fdir = tmp_path / "fragments"
    out_file = tmp_path / "credit_content_20261107.json"
    builder.split_content("20261107", fdir=fdir)
    for ch in ("figures", "brief", "topics", "tail", "all"):
        assert builder.check_fragments("20261107", chunk=ch, fdir=fdir) == []
    assembled = builder.assemble_content("20261107", fdir=fdir, out=out_file)
    canonical = load_json(content_path("20261107"))
    assert assembled == canonical


def test_20261107_sod_dossier_passes_full_guard_and_renders(registry):
    from ops_chrizza_dossier_common import content_path, evidence_path, load_json, output_path, prior_content
    from ops_chrizza_learning_ledger import load_ledger
    c_261107 = load_json(content_path("20261107"))
    ev_261107 = load_json(evidence_path("20261107"))
    defects = guard.check_evidence(ev_261107)
    defects += guard.check_gap_feeds("20261107")
    defects += guard.check_content(c_261107, ev_261107, registry, load_ledger(), prior_content("20261107"))
    assert defects == []
    html_file = output_path("20261107")
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert guard.check_html(html_text) == []
    assert "post-Thufir*" in html_text

