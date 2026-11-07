"""Chrizza structured credit & CLO horizon dossier engine (v3).

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (operator intelligence publishing)
    Classifier    : CC-Bear · RC-Butterfly with roc/scripts/ops_thufir (pipeline shape)
    Lock status   : UNLOCKED — awaiting Agent Manager ratification

Separation of concerns:
    evidence JSON  — dated capture notes, sealed with sha256(excerpt)     (Observe)
    quotes JSON    — live FMP credit/CLO/BDC proxy tape, sealed sha256    (Observe)
    content JSON   — figures registry + prose using [[Fxx]] tokens        (Orient / Decide)
    vectors JSON   — emitted StructuredCreditSignalRecord for alpha-g     (Act)
    call ledger    — scored track record that caps conviction             (Reflect)
    template       — content-free HTML shell (canonical + runtime mirror) (Act)
The engine refuses to render while the content or HTML guard reports any defect.

CLI:
    seal          --date YYYYMMDD   seal evidence excerpts (run once, at capture time)
    sweep-quotes  --date YYYYMMDD   sweep & seal live FMP CLO/loan/BDC quotes + Treasury curve
    render        --date YYYYMMDD   guard content, emit vectors, render & verify dossier HTML
    sync-template                   copy the canonical template to the runtime mirror
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    BLOCK_PROVENANCE,
    CANONICAL_TEMPLATE,
    CREDIT_PROXY_META,
    CREDIT_PROXY_SYMBOLS,
    HERE,
    INFINIX_SVG_PATH,
    LATEX_STATUS,
    LEDGER_PATH,
    MIRROR_TEMPLATE,
    NON_CLAIM_KEYS,
    ORIGINS,
    PROVENANCE,
    ROOT,
    SCHEMA_QUOTES,
    SCHEMA_VECTORS,
    SGC_LOGO_SOURCE,
    TOKEN_RE,
    WATCHLIST_PATH,
    bond_isins_path,
    clo_tranches_path,
    content_path,
    court_dockets_path,
    evidence_path,
    load_json,
    load_registry,
    load_watchlist,
    nbfi_bdc_path,
    output_path,
    parse_utc,
    prior_content,
    quotes_path,
    save_json,
    seal_payload,
    sha256_file,
    sha256_text,
    vectors_path,
)
from ops_chrizza_learning_ledger import conviction_band, conviction_cap, load_ledger, stats  # noqa: E402
from ops_chrizza_pre_publish_guard import (  # noqa: E402
    check_content,
    check_evidence,
    check_gap_feeds,
    check_html,
    check_quotes,
    check_template_sync,
)

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
SLOT_RE = re.compile(r"\{\{[A-Z_]+\}\}")
CREED = "O paliós eínai alliós, allá o néos eínai oraíos."
FMP_BASE = "https://financialmodelingprep.com/stable"

# Presentation only: tranche colours from senior (gold) to equity (red). Tranche data lives in content.
TRANCHE_COLOURS = ("#f2d27e", "#e4bd62", "#d4a843", "#c09ad2", "#a07cb3", "#eba33f", "#e9606b")
SECTION_TITLES = ("Signal — what moved", "Forensic mechanism", "Factor map",
                  "Scenarios & kill switch", "Positioning & verification")
SECTION_BLOCKS = ("signal", "mechanism", "factors", "scenarios", "posture")
TAB_LABELS = {0: "Command Brief", 7: "Provenance & Ledger"}
# One sentence per key, used for every badge tooltip and the front-page legend.
KEY_MEANING = {
    "sourced": "Sourced — restated from a sealed capture note or live FMP snapshot (see Provenance & Ledger)",
    "derived": "Derived — computed from sourced figures, or exact by definition",
    "estimate": "Estimate — Chrizza judgement; falsifiable ones are scored in the call ledger",
    "illustrative": "Illustrative — a teaching example or interactive waterfall stress model, not live market data",
    "gap": "Gap — data missing; no claim is made",
}
assert set(KEY_MEANING) == set(PROVENANCE) | set(NON_CLAIM_KEYS), "KEY_MEANING must cover the key exactly"


# ── Text helpers ──────────────────────────────────────────────────────────
def esc(value: Any) -> str:
    """HTML-escape any value."""
    return html.escape(str(value), quote=True)


def figure_span(fid: str, figures: dict[str, Any]) -> str:
    """Provenance-coloured span for a figure, with its audit trail in the tooltip."""
    fig = figures[fid]
    parts = [f"{fid} · {fig['label']}", fig["provenance"]]
    if fig.get("as_of"):
        parts.append(f"as of {fig['as_of']}")
    if fig.get("evidence"):
        parts.append(f"evidence {fig['evidence']}")
    parts.append(f"confidence {fig['confidence']}")
    if fig.get("historical"):
        parts.append("historical")
    if fig.get("rationale"):
        parts.append(fig["rationale"])
    return (f'<span class="fig fig-{fig["provenance"]}" title="{esc(" · ".join(parts))}">'
            f'{html.escape(fig["display"])}</span>')


def fmt(text: str, figures: dict[str, Any]) -> str:
    """Escape prose, then apply **bold** and resolve [[Fxx]] figure tokens."""
    out = html.escape(text, quote=False)
    out = BOLD_RE.sub(r"<strong>\1</strong>", out)
    return TOKEN_RE.sub(lambda m: figure_span(m.group(1), figures), out)


def tag(text: str, colour: str) -> str:
    """Small coloured tag."""
    return f'<span class="tag tag-{colour}">{esc(text)}</span>'


def topic_tag(tid: str) -> str:
    """Clickable topic jump pill (e.g. T1 -> switchTab('tab-1'))."""
    m = re.fullmatch(r"T([1-6])", tid.strip())
    if not m:
        return tag(tid, "cyan")
    idx = m.group(1)
    return (f'<span class="tag tag-cyan tag-jump" role="button" tabindex="0" '
            f'title="Click to jump to Topic {esc(tid)}" onclick="switchTab(\'tab-{idx}\')">{esc(tid)}</span>')


def kbadge(key: str) -> str:
    """Key badge: one of the four provenance classes, or a non-claim marker."""
    return f'<span class="kbadge kb-{key}" title="{esc(KEY_MEANING[key])}">{key}</span>'


def est_span(display: str, title: str) -> str:
    """Inline estimate (e.g. a scenario probability), styled exactly like an estimate figure."""
    return f'<span class="fig fig-estimate" title="{esc(title)} · estimate">{esc(display)}</span>'


# ── Brand marks (read from source, never hand-copied) ─────────────────────
def infinix_svg() -> str:
    """Infinix mark from the UI asset, resized for the masthead."""
    svg, n = re.subn(r'width="316"\s+height="156"', 'width="52" height="26"',
                     INFINIX_SVG_PATH.read_text(encoding="utf-8"), count=1)
    if n != 1:
        raise RuntimeError("Infinix SVG root size attributes not found — asset changed")
    return svg.strip()


def sgc_svg() -> str:
    """SGC mark extracted from the top status bar component."""
    source = SGC_LOGO_SOURCE.read_text(encoding="utf-8")
    start = source.index('class="company-logo"')
    match = re.search(r'<svg viewBox="0 0 210 180"[^>]*>.*?</svg>', source[start:], re.DOTALL)
    if not match:
        raise RuntimeError("SGC logo SVG not found in sgc-top-status-bar.ts")
    return match.group(0).replace('<svg viewBox="0 0 210 180"', '<svg viewBox="0 0 210 180" width="34" height="30"', 1)


# ── Visual builders ───────────────────────────────────────────────────────
def gauge_svg(score: float) -> str:
    """Semicircular regime gauge: −100 risk-off (left) to +100 risk-on (right)."""
    cx, cy, r = 130, 135, 100
    theta = math.pi * (1 - (score + 100) / 200)
    nx, ny = cx + 82 * math.cos(theta), cy - 82 * math.sin(theta)
    ticks = []
    for t in (-100, -50, 0, 50, 100):
        a = math.pi * (1 - (t + 100) / 200)
        x1, y1 = cx + 88 * math.cos(a), cy - 88 * math.sin(a)
        x2, y2 = cx + 112 * math.cos(a), cy - 112 * math.sin(a)
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#0b1222" stroke-width="3"/>')
    return f"""<svg viewBox="0 0 260 170" width="300" height="196" role="img" aria-label="Regime gauge">
  <defs><linearGradient id="gaugeGrad" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0" stop-color="#e9606b"/><stop offset="0.5" stop-color="#eba33f"/><stop offset="1" stop-color="#4cc493"/>
  </linearGradient></defs>
  <path d="M {cx - r} {cy} A {r} {r} 0 0 1 {cx + r} {cy}" fill="none" stroke="url(#gaugeGrad)" stroke-width="22" stroke-linecap="round"/>
  {''.join(ticks)}
  <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>
  <circle cx="{cx}" cy="{cy}" r="9" fill="#d4a843" stroke="#0b1222" stroke-width="3"/>
  <text x="{cx - r}" y="{cy + 26}" fill="#8a97b0" font-family="Fira Code" font-size="10" text-anchor="middle">RISK-OFF</text>
  <text x="{cx + r}" y="{cy + 26}" fill="#8a97b0" font-family="Fira Code" font-size="10" text-anchor="middle">RISK-ON</text>
  <text x="{cx}" y="{cy - 34}" fill="#ffffff" font-family="Inter" font-size="30" font-weight="900" text-anchor="middle">{score:+.0f}</text>
</svg>"""


def heatmap_html(topics: list[dict]) -> str:
    """5×5 probability × impact map of the dossier's topics (clickable tags jump to topic tab)."""
    tab_idx = {t["id"]: i + 1 for i, t in enumerate(topics)}
    cells = []
    for prob in range(5, 0, -1):
        cells.append(f'<div class="axis">{prob}</div>')
        for impact in range(1, 6):
            hue = 150 - 150 * (prob * impact - 1) / 24
            dots = "".join(
                f'<span class="dot" title="{esc(t["title"])} — click to open Tab {tab_idx[t["id"]]}" '
                f'onclick="switchTab(\'tab-{tab_idx[t["id"]]}\')">{esc(t["emoji"])} {esc(t["id"])}</span>'
                for t in topics if t["risk"]["probability"] == prob and t["risk"]["impact"] == impact
            )
            cells.append(f'<div class="cell" style="background: hsla({hue:.0f}, 62%, 45%, 0.30)">{dots}</div>')
    return (f'<div class="heatmap">{"".join(cells)}</div>'
            '<div class="heat-axis-label"><span>↑ probability</span><span>impact →</span></div>')


def stack_html(t: dict[str, Any], figures: dict[str, Any]) -> str:
    """Illustrative capital stack + Interactive CLO 2.0 Waterfall & Subordination Stress Simulator."""
    fig = figures[t["show_stack"]]
    rows = "".join(
        f'<div class="tranche" style="flex: {share}; background: {TRANCHE_COLOURS[i % len(TRANCHE_COLOURS)]}">'
        f'<span>{esc(name)}</span><span>{share:g}%</span></div>'
        for i, (name, share) in enumerate(fig["tranches"])
    )
    tranche_cards = "".join(
        f'<div class="sim-t"><div class="tn">{esc(name)}</div><div class="ts">{share:g}% par</div>'
        f'<div class="ti imp-safe" id="sim-tr-{esc(name)}">0.0% loss</div></div>'
        for name, share in fig["tranches"]
    )
    sim = f"""<div class="sim-panel" data-prov="illustrative">
  <div class="sim-header">
    <h4>Interactive CLO 2.0 Waterfall &amp; Subordination Stress Simulator {kbadge("illustrative")}</h4>
    <div class="sim-presets">
      <button type="button" class="sim-btn" onclick="setSimPreset(3.6, 60, 5.5, this)">1Y Base (3.6% CDR / 60% Rec)</button>
      <button type="button" class="sim-btn" onclick="setSimPreset(4.5, 55, 7.2, this)">Fitch 2026 Forecast (4.5% / 55%)</button>
      <button type="button" class="sim-btn active" onclick="setSimPreset(15.0, 50, 9.5, this)">3Y Protracted Stress (15% Cumul / 50%)</button>
      <button type="button" class="sim-btn" onclick="setSimPreset(22.0, 35, 14.0, this)">LME Priming Tail (22% Cumul / 35%)</button>
    </div>
  </div>
  <div class="sim-controls">
    <div class="sim-ctrl">
      <label><span>Cumulative Default Rate (CDR)</span><strong id="sim-cdr-val">15.0%</strong></label>
      <input type="range" id="sim-cdr" min="0" max="35" step="0.5" value="15.0" oninput="updateWaterfallSim()">
    </div>
    <div class="sim-ctrl">
      <label><span>Portfolio Recovery Rate (R)</span><strong id="sim-rec-val">50%</strong></label>
      <input type="range" id="sim-rec" min="20" max="80" step="5" value="50" oninput="updateWaterfallSim()">
    </div>
    <div class="sim-ctrl">
      <label><span>CCC Bucket Share (7.5% Limit)</span><strong id="sim-ccc-val">9.5%</strong></label>
      <input type="range" id="sim-ccc" min="2" max="20" step="0.5" value="9.5" oninput="updateWaterfallSim()">
    </div>
  </div>
  <div class="sim-readout">
    <div class="sim-stat"><span class="sk">Net Collateral Par Loss</span><span class="sv" id="sim-loss-out">7.50% par</span></div>
    <div class="sim-stat"><span class="sk">Excess CCC Haircut (30% MV)</span><span class="sv" id="sim-haircut-out">0.60% par</span></div>
    <div class="sim-stat"><span class="sk">Junior OC Cushion (450 bps init)</span><span class="sv" id="sim-oc-out">-360 bps</span></div>
    <div class="sim-stat"><span class="sk">Interest Diversion Gate</span><span class="sv" id="sim-div-out">TRIPPED · AAA PAYDOWN</span></div>
  </div>
  <div class="sim-tranches">{tranche_cards}</div>
</div>"""
    return (f'<div class="stack-wrap" data-prov="illustrative"><div class="stack" title="{esc(fig["rationale"])}">{rows}</div>'
            f'<div class="prose small"><p>{kbadge("illustrative")} <strong>{esc(fig["label"])}</strong> — {esc(fig["rationale"])}</p>'
            f'<p>{fmt(t["stack_note"], figures)}</p>{sim}</div></div>')


def integrity_html(figures: dict[str, Any], gaps: list[dict]) -> str:
    """Stacked bar of figures by provenance, plus open data gaps."""
    counts = {p: sum(1 for f in figures.values() if f["provenance"] == p) for p in PROVENANCE}
    total = sum(counts.values()) + len(gaps)
    segs = "".join(f'<span class="prov-{p}" style="width: {100 * n / total:.2f}%"></span>' for p, n in counts.items() if n)
    segs += f'<span class="prov-gap" style="width: {100 * len(gaps) / total:.2f}%"></span>' if gaps else ""
    legend = "".join(f'<span title="{esc(KEY_MEANING[p])}"><i class="prov-{p}"></i>{p} · {n}</span>' for p, n in counts.items())
    legend += f'<span title="{esc(KEY_MEANING["gap"])}"><i class="prov-gap"></i>open gaps · {len(gaps)}</span>'
    return f'<div class="integrity">{segs}</div><div class="legend">{legend}</div>'


def provenance_legend() -> str:
    """Front-page key and the rule it enforces."""
    items = "".join(f'<span title="{esc(KEY_MEANING[p])}"><i class="prov-{p}"></i>{p}</span>' for p in PROVENANCE)
    return (f'<div class="legend">{items}</div><p class="key-rule">Every number, chart and section in this dossier '
            'carries one of these four keys — figures by underline colour, sections by badge; hover either for its audit trail. '
            'Open data gaps are marked separately and are not claims.</p>')


def card(title: str, body: str, *, block: str | None = None, key: str | None = None, extra: str = "",
         count: str = "", prov: str | None = None) -> str:
    """Glass card whose title carries the key badge of its block type (or an explicit key)."""
    cnt = f'<span class="count">{esc(count)}</span>' if count else ""
    badge_key = key or (BLOCK_PROVENANCE[block] if block else None)
    badge = kbadge(badge_key) if badge_key else ""
    attr = f' data-prov="{prov}"' if prov else ""
    return f'<div class="card {extra}"{attr}><h3 class="card-title">{esc(title)} {cnt}{badge}</h3>{body}</div>'


def table(headers: list[str | tuple[str, str]], rows: list[list[str]], *,
          table_id: str = "", row_attrs: list[str] | None = None) -> str:
    """Table with optional institutional <th> hover tooltips and row attributes."""
    ths = []
    n = len(headers)
    for idx, h in enumerate(headers):
        if isinstance(h, tuple):
            label, tip = h
            edge = " tip-left" if idx == 0 else (" tip-right" if idx == n - 1 else "")
            ths.append(f'<th><span class="th-tip{edge}" data-tooltip="{esc(tip)}" title="{esc(tip)}">{esc(label)}</span></th>')
        else:
            ths.append(f"<th>{esc(h)}</th>")
    head = "".join(ths)
    tr_list = []
    for i, r in enumerate(rows):
        attr = f" {row_attrs[i]}" if row_attrs and i < len(row_attrs) and row_attrs[i] else ""
        tr_list.append(f"<tr{attr}>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    tid = f' id="{esc(table_id)}"' if table_id else ""
    return f'<div class="tbl-wrap"><table class="tbl"{tid}><thead><tr>{head}</tr></thead><tbody>{"".join(tr_list)}</tbody></table></div>'


def _delta_span(val: float | None, suffix: str = "%") -> str:
    if val is None:
        return '<span class="delta-neu">—</span>'
    cls = "delta-pos" if val > 0.02 else ("delta-neg" if val < -0.02 else "delta-neu")
    return f'<span class="{cls}">{val:+.2f}{suffix}</span>'


def proxy_tape_html(quotes_doc: dict[str, Any] | None) -> str:
    """Render the sealed FMP liquid credit, CLO & BDC proxy tape card for Tab 0."""
    if not quotes_doc or not quotes_doc.get("quotes"):
        return ""
    qmap = quotes_doc["quotes"]
    tsy = quotes_doc.get("treasury") or {}
    curve_html = ""
    if tsy:
        y2, y10 = tsy.get("year2"), tsy.get("year10")
        slope_bp = round((y10 - y2) * 100) if (isinstance(y2, (int, float)) and isinstance(y10, (int, float))) else None
        pills = [
            f'<span class="c-pill">3M <b>{tsy.get("month3", "—")}%</b></span>',
            f'<span class="c-pill">2Y <b>{tsy.get("year2", "—")}%</b></span>',
            f'<span class="c-pill">5Y <b>{tsy.get("year5", "—")}%</b></span>',
            f'<span class="c-pill">10Y <b>{tsy.get("year10", "—")}%</b></span>',
            f'<span class="c-pill">30Y <b>{tsy.get("year30", "—")}%</b></span>',
        ]
        if slope_bp is not None:
            pills.append(f'<span class="c-pill">2s10s Slope <b>{slope_bp:+d} bps</b></span>')
        curve_html = (f'<div class="curve-strip"><span>🏛️ US Sovereign Curve ({esc(tsy.get("date", "latest"))}):</span>'
                      + "".join(pills)
                      + f'<span class="mono muted" style="margin-left:auto">Seal: {esc(quotes_doc["sha256"][:12])}…</span></div>')

    headers: list[str | tuple[str, str]] = [
        ("Ticker", "Exchange-traded structured credit, senior loan, corporate bond or BDC ticker"),
        ("Instrument", "Full fund or BDC name from sealed FMP snapshot"),
        ("Segment", "Role in the structured credit & leveraged finance capital stack"),
        ("Price", "Latest Point-in-Time market price (USD)"),
        ("1D Chg", "1-session percentage price change"),
        ("vs 50D MA", "Percentage distance from 50-day moving average (tactical trend)"),
        ("vs 200D MA", "Percentage distance from 200-day moving average (secular regime)"),
        ("52W Range Position", "Current price percentile within the 52-week low-to-high range"),
        ("vs 52W High", "Percentage drawdown from 52-week high (credit dispersion gauge)"),
    ]
    rows = []
    for sym, label, role in CREDIT_PROXY_META:
        item = qmap.get(sym)
        if not item:
            continue
        px = item.get("price") or 0.0
        chg = item.get("changePercentage")
        d50 = item.get("delta50Pct")
        d200 = item.get("delta200Pct")
        dd_high = item.get("drawdownHighPct")
        yr_low = item.get("yearLow") or px
        yr_high = item.get("yearHigh") or px
        pct_range = max(0.0, min(100.0, 100.0 * (px - yr_low) / (yr_high - yr_low))) if yr_high > yr_low else 50.0
        range_cell = (f'<div class="range-wrap"><span>${yr_low:.2f}</span>'
                      f'<div class="range-bar"><span class="range-fill" style="width:{pct_range:.1f}%"></span></div>'
                      f'<span>${yr_high:.2f}</span></div>')
        seg_col = "green" if "AAA" in role or "IG" in role else ("amber" if "Mezz" in role or "BSL" in role else "mauve")
        rows.append([
            f'<span class="mono"><strong>${esc(sym)}</strong></span>',
            esc(item.get("name") or label),
            tag(role, seg_col),
            f'<span class="mono"><strong>${px:.2f}</strong></span>',
            _delta_span(chg),
            _delta_span(d50),
            _delta_span(d200),
            range_cell,
            _delta_span(dd_high),
        ])
    body = curve_html + table(headers, rows)
    return f'<div class="section-gap">{card("Liquid Structured Credit, Senior Loan & BDC Proxy Tape (Sealed FMP Snapshot)", body, block="proxy_tape", count=f"{len(rows)} instruments", prov="sourced")}</div>'


def _watchlist_themes() -> tuple[dict[str, str], dict[str, str]]:
    """Return (isin -> theme, theme -> label) from the watchlist; empty maps if it is absent."""
    if not WATCHLIST_PATH.exists():
        return {}, {}
    wl = load_watchlist()
    isin_theme = {b["isin"]: b.get("theme", "") for b in wl.get("bonds", [])}
    labels = {k: v.get("label", k) for k, v in (wl.get("themes") or {}).items()}
    return isin_theme, labels


def theme_topic_map(topics: list[dict[str, Any]]) -> dict[str, str]:
    """Theme -> topic id, claimed explicitly by today's topics via `watch_themes` (never hardcoded)."""
    return {theme: t["id"] for t in topics for theme in t.get("watch_themes", [])}


def bond_isins_html(bond_doc: dict[str, Any] | None, topics: list[dict[str, Any]] | None = None) -> str:
    """Render Gap G5 live European exchange Eurobond & WBS ISIN bid-ask tape on Tab 0.

    Theme aggregates are computed from the bonds themselves; a bond links to a topic tab only when
    a current topic claims its watch-list theme. Unclaimed themes show as surveillance-only tags.
    """
    if not bond_doc or not bond_doc.get("bonds"):
        return ""
    isin_theme, theme_labels = _watchlist_themes()
    claimed = theme_topic_map(topics or [])
    bonds = bond_doc["bonds"]

    def theme_of(b: dict[str, Any]) -> str:
        return b.get("theme") or isin_theme.get(b["isin"], "unassigned")

    pills = []
    for theme in dict.fromkeys(theme_of(b) for b in bonds):
        group = [b for b in bonds if theme_of(b) == theme]
        avg = sum(float(b["mid"]) for b in group) / len(group)
        bids = [float(b["bid"]) for b in group if b.get("bid") is not None]
        low_bid = f" · low bid {min(bids):.2f}" if bids else ""
        pills.append(f'<span class="c-pill">{esc(theme_labels.get(theme, theme))} avg mid '
                     f'<strong class="px-dn">{avg:.2f} pts</strong>{low_bid}</span>')
    low = min(bonds, key=lambda x: float(x["mid"]))
    strip = (
        f'<div class="curve-strip">'
        f'<span><b>EUROBOND ISIN ORDER BOOK</b> ({esc(str(bond_doc.get("captured_at_utc", "—")))})</span>'
        + "".join(pills)
        + f'<span class="c-pill">Deepest Distress <strong class="px-dn">{esc(low["isin"])} @ {float(low["mid"]):.2f} pts</strong></span>'
        f'</div>'
    )
    headers: list[str | tuple[str, str]] = [
        ("ISIN", "12-character Eurobond or Reg S security identifier"),
        ("Issuer & Tranche", "Legal issuing vehicle, coupon, currency and maturity"),
        ("Seniority", "Capital-structure rank (Class A WBS, Senior Secured, Senior Unsecured, VFN)"),
        ("Topic", "Today's dossier topic claiming this watch-list theme (click to jump); 'watch-list' = surveillance only, no current topic"),
        ("Venue / CCY", "European regulated or MTF exchange venue and quote currency"),
        ("Clean Bid", "Executable exchange order-book bid clean price (% of par)"),
        ("Clean Ask", "Executable exchange order-book ask clean price (% of par)"),
        ("Mid (pts)", "Two-sided clean mid price (% of par)"),
        ("Bid–Ask", "Order-book bid-ask width in clean price points"),
        ("52W High", "Trailing 1-year high clean price (% of par)"),
        ("1Y Drawdown", "Percentage decline from trailing 52-week high clean price"),
    ]
    rows = []
    for b in bonds:
        theme = theme_of(b)
        topic_cell = topic_tag(claimed[theme]) if theme in claimed else tag("watch-list", "mauve")
        mid = float(b.get("mid") or 0.0)
        mid_cls = "px-dn" if mid < 70.0 else ("px-flat" if mid < 90.0 else "px-up")
        dd = b.get("drawdown_1y_pct")
        dd_str = f"{float(dd):+.2f}%" if dd is not None else "—"
        hi = b.get("high_1y")
        hi_str = f"{float(hi):.2f}" if hi is not None else "—"
        bid_str = f'{float(b["bid"]):.2f}' if b.get("bid") is not None else "—"
        ask_str = f'{float(b["ask"]):.2f}' if b.get("ask") is not None else "—"
        rows.append([
            f'<span class="mono"><strong>{esc(b["isin"])}</strong></span>',
            esc(b["label"]),
            esc(b["seniority"]),
            topic_cell,
            f'<span class="mono">{esc(b["venue"])} · {esc(b["currency"])}</span>',
            f'<span class="mono">{bid_str}</span>',
            f'<span class="mono">{ask_str}</span>',
            f'<span class="mono {mid_cls}"><strong>{mid:.2f}</strong></span>',
            f'<span class="mono">{float(b.get("bid_ask_spread_pts") or 0.0):.2f}</span>',
            f'<span class="mono">{hi_str}</span>',
            f'<span class="mono px-dn">{dd_str}</span>' if dd is not None and float(dd) < -10.0 else f'<span class="mono">{dd_str}</span>',
        ])
    return f'<div class="section-gap">{card("Benchmark Eurobond & UK WBS ISIN Order-Book Tape (Sealed Stuttgart / Frankfurt Snapshot — Gap G5)", strip + table(headers, rows), block="bond_isins", count=f"{len(rows)} ISINs", prov="sourced")}</div>'


def nbfi_bdc_html(nbfi_doc: dict[str, Any] | None) -> str:
    """Render Gaps G3 & G4 FRED NDFI/OAS macro strip and SEC EDGAR Form 10-Q BDC XBRL PIK table on Tab 0."""
    if not nbfi_doc or not nbfi_doc.get("bdc_records"):
        return ""
    fs = nbfi_doc.get("fred_series", {})
    fd = nbfi_doc.get("fred_derived", {})
    bs = nbfi_doc.get("bdc_pik_summary", {})
    ndfi_val = fs.get("LNFACBW027SBOG", {}).get("value", 0.0)
    ndfi_dt = fs.get("LNFACBW027SBOG", {}).get("as_of", "—")
    eur_oas = fs.get("BAMLHE00EHYIOAS", {}).get("value", 0.0)
    us_oas = fs.get("BAMLH0A0HYM2", {}).get("value", 0.0)
    bb_oas = fs.get("BAMLH0A1HYBB", {}).get("value", 0.0)
    b_oas = fs.get("BAMLH0A2HYB", {}).get("value", 0.0)
    ccc_oas = fs.get("BAMLH0A3HYC", {}).get("value", 0.0)
    strip = (
        f'<div class="curve-strip">'
        f'<span><b>FRED H.8 &amp; ICE BofA OAS</b></span>'
        f'<span class="c-pill">US Bank Loans to NDFIs <b>${float(ndfi_val):,.2f}bn</b> '
        f'({fd.get("ndfi_share_of_total_bank_loans_pct", 0):.2f}% of Bank Credit, {esc(str(ndfi_dt))})</span>'
        f'<span class="c-pill">EUR HY OAS <b>{float(eur_oas):.2f}%</b> vs US HY <b>{float(us_oas):.2f}%</b> '
        f'({fd.get("eur_minus_us_hy_oas_bp", 0):+.0f} bps)</span>'
        f'<span class="c-pill">US BB <b>{float(bb_oas):.2f}%</b> · Single-B <b>{float(b_oas):.2f}%</b> · '
        f'CCC <strong class="px-dn">{float(ccc_oas):.2f}%</strong> (+{fd.get("us_ccc_minus_bb_oas_bp", 0):.0f} bps CCC–BB)</span>'
        f'<span class="c-pill">BDC Avg Total PIK <strong class="px-dn">{bs.get("equal_weighted_pik_share_pct") or 0:.2f}%</strong></span>'
        f'</div>'
    )
    headers: list[str | tuple[str, str]] = [
        ("BDC", "Publicly traded US Business Development Company ticker"),
        ("Entity Name", "SEC EDGAR registrant name"),
        ("Period End", "Latest filed Form 10-Q / 10-K fiscal quarter end"),
        ("Filed", "SEC EDGAR filing date"),
        ("QTD Gross Inc ($m)", "Quarterly GrossInvestmentIncomeOperating in USD millions"),
        ("PIK Debt Int %", "Quarterly non-cash PIK debt interest as % of Gross Investment Income"),
        ("PIK Div %", "Quarterly non-cash PIK preferred dividend income as % of Gross Investment Income"),
        ("Total PIK %", "Combined non-cash PIK income share of Gross Investment Income"),
        ("XBRL Basis", "Matched-window methodology: QTD_DIRECT or 90-day YTD_DELTA_IMPLIED_QTD"),
    ]
    rows = []
    for r in nbfi_doc["bdc_records"]:
        tot_pik = r.get("pik_share_pct")
        int_pik = r.get("pik_interest_share_pct")
        div_pik = r.get("pik_dividend_share_pct")
        pik_cls = "px-dn" if (tot_pik is not None and float(tot_pik) >= 10.0) else "px-flat"
        rows.append([
            f'<span class="mono"><strong>{esc(r["symbol"])}</strong></span>',
            esc(r["name"]),
            f'<span class="mono">{esc(r["latest_period_end"])}</span>',
            f'<span class="mono">{esc(r["latest_filed"])}</span>',
            f'<span class="mono">${float(r["latest_GrossIncome_qtd_usd_m"]):,.2f}m</span>',
            f'<span class="mono">{float(int_pik):.2f}%</span>' if int_pik is not None else '<span class="mono muted">—</span>',
            f'<span class="mono">{float(div_pik):.2f}%</span>' if div_pik is not None else '<span class="mono muted">—</span>',
            f'<span class="mono {pik_cls}"><strong>{float(tot_pik):.2f}%</strong></span>' if tot_pik is not None else '<span class="mono muted">Footnote only</span>',
            f'<span class="mono muted">{esc(r["pik_calculation_basis"])}</span>',
        ])
    return f'<div class="section-gap">{card("Statutory Fed H.8 Bank-to-NDFI Lending, Credit OAS & SEC EDGAR BDC XBRL PIK Monitor (Gaps G3 & G4)", strip + table(headers, rows), block="nbfi_bdc", count=f"{len(rows)} BDCs + 9 FRED series", prov="sourced")}</div>'


def clo_tranches_html(clo_doc: dict[str, Any] | None) -> str:
    """Render Gap G1 SEC EDGAR Form NPORT-P deal-level CLO tranche telemetry on Tab 7."""
    if not clo_doc or not clo_doc.get("etf_tranche_pools"):
        return ""
    s = clo_doc.get("summary", {})
    pool_headers: list[str | tuple[str, str]] = [
        ("Pool", "CLO ETF ticker"),
        ("SEC Series", "Form NPORT-P registered series name"),
        ("Report Date", "Form NPORT-P portfolio valuation date"),
        ("CLO Tranches", "Count of individual deal-level CLO tranches parsed from XML"),
        ("CLO Par ($m)", "Aggregate CLO tranche principal par held in USD millions"),
        ("Par-Wtd Price", "Par-weighted clean/fair valuation mark (% of par)"),
        ("Par-Wtd Coupon", "Par-weighted annualized floating coupon (%)"),
        ("Tranches < 99", "Count and share of individual CLO tranches marked below 99.0 pts"),
        ("Min / Max Mark", "Lowest and highest individual deal tranche fair-value mark in the pool"),
        ("Top Manager Shelves", "Largest CLO collateral manager exposures by par"),
    ]
    pool_rows = []
    tranche_rows = []
    for p in clo_doc["etf_tranche_pools"]:
        shelves = ", ".join(f'{m["shelf"]} (${m["par_usd_m"]:.0f}m)' for m in p.get("top_manager_shelves", [])[:3])
        b99 = int(p.get("tranches_below_99_count", 0))
        b99_cls = "px-dn" if b99 > 0 else "px-up"
        arch_url = p.get("archive_url") or ""
        sym_cell = (f'<a class="mono ext-link" href="{esc(arch_url)}" target="_blank" rel="noopener noreferrer" '
                    f'title="Open SEC EDGAR Form NPORT-P XML filing"><strong>{esc(p["symbol"])} ↗</strong></a>'
                    if arch_url else f'<span class="mono"><strong>{esc(p["symbol"])}</strong></span>')
        pool_rows.append([
            sym_cell,
            esc(p["series_name"]),
            f'<span class="mono">{esc(p["report_period_date"])}</span>',
            f'<span class="mono"><strong>{p["clo_tranche_count"]}</strong></span>',
            f'<span class="mono">${float(p["clo_par_usd_m"]):,.1f}m</span>',
            f'<span class="mono">{float(p["par_weighted_fair_price"]):.2f}</span>',
            f'<span class="mono">{float(p["par_weighted_coupon_pct"]):.2f}%</span>',
            f'<span class="mono {b99_cls}">{b99} ({float(p["tranches_below_99_pct"]):.2f}%)</span>',
            f'<span class="mono">{float(p["min_tranche_price"]):.2f} / {float(p["max_tranche_price"]):.2f}</span>',
            esc(shelves),
        ])
        for t in p.get("representative_tranches", [])[:4]:
            px = float(t["clean_fair_price"])
            px_cls = "px-dn" if px < 98.5 else ("px-flat" if px < 99.9 else "px-up")
            cpn = f'{float(t["coupon_pct"]):.2f}%' if t.get("coupon_pct") is not None else "—"
            tranche_rows.append([
                tag(p["symbol"], "cyan"),
                esc(t["tranche"]),
                f'<span class="mono">{esc(t["isin"] or t["cusip"])}</span>',
                f'<span class="mono">${float(t["par_usd_m"]):,.2f}m</span>',
                f'<span class="mono {px_cls}"><strong>{px:.2f}</strong></span>',
                f'<span class="mono">{cpn}</span>',
                f'<span class="mono">{esc(t.get("maturity") or "—")}</span>',
            ])
    tranche_headers: list[str | tuple[str, str]] = [
        ("Pool", "Parent Form NPORT-P ETF pool"),
        ("Deal & Tranche", "Individual CLO issuer, series, and rated class"),
        ("ISIN / CUSIP", "Tranche security identifier"),
        ("Par Held", "Principal balance held in USD millions"),
        ("Fair Mark (pts)", "Fund valuation mark (% of par)"),
        ("Floating Coupon", "Annualized floating rate (%) reported in debtSec"),
        ("Stated Maturity", "Legal final maturity date"),
    ]
    body = (
        table(pool_headers, pool_rows)
        + '<p class="small muted section-gap">Representative &amp; discount-tail deal-level CLO tranches extracted from Form NPORT-P XML:</p>'
        + table(tranche_headers, tranche_rows)
    )
    tot = s.get("total_deal_tranches_parsed", 0)
    return f'<div class="section-gap">{card("SEC EDGAR Form NPORT-P Deal-Level CLO Tranche Telemetry (Gap G1 Narrowed)", body, block="clo_tranches", count=f"{tot} tranches", prov="sourced")}</div>'


def court_dockets_html(dockets_doc: dict[str, Any] | None) -> str:
    """Render Gap G2 UK High Court Case Law XML & SEC EFTS restructuring filings on Tab 7."""
    if not dockets_doc:
        return ""
    uk = dockets_doc.get("uk_high_court_judgments") or []
    sec = dockets_doc.get("sec_restructuring_filings") or []
    if not uk and not sec:
        return ""
    headers: list[str | tuple[str, str]] = [
        ("Jurisdiction", "Statutory source: UK National Archives Case Law XML or SEC EDGAR EFTS"),
        ("Scope", "Monitored restructuring / LME docket stream"),
        ("Case Title / Registrant", "Court caption or SEC registrant name"),
        ("Court / Form", "Neutral citation path (e.g. ewhc/ch) or SEC form type"),
        ("Date", "Publication or SEC filing date"),
        ("Statutory Reference", "Accession or canonical court docket path"),
    ]
    rows = []
    for j in uk[:6]:
        jurl = j.get("judgment_url") or ""
        ref_cell = (f'<a class="mono ext-link" href="{esc(jurl)}" target="_blank" rel="noopener noreferrer">{esc(jurl)} ↗</a>'
                    if jurl.startswith("https://") else f'<span class="mono">{esc(jurl)}</span>')
        rows.append([
            tag("UK COURT XML", "amber"),
            esc(j["query_label"]),
            f'<strong>{esc(j["case_title"])}</strong>',
            f'<span class="mono">{esc(j["court_path"])}</span>',
            f'<span class="mono">{esc(j["published_utc"][:10])}</span>',
            ref_cell,
        ])
    for f_rec in sec[:8]:
        furl = f_rec.get("archive_url") or ""
        label_ref = f'{f_rec["accession"]} · {f_rec["document"]}'
        ref_cell = (f'<a class="mono ext-link" href="{esc(furl)}" target="_blank" rel="noopener noreferrer">{esc(label_ref)} ↗</a>'
                    if furl.startswith("https://") else f'<span class="mono">{esc(label_ref)}</span>')
        rows.append([
            tag("SEC EFTS", "cyan"),
            esc(f_rec["query_label"]),
            esc(f_rec["entity"]),
            f'<span class="mono">{esc(f_rec["form"])}</span>',
            f'<span class="mono">{esc(f_rec["file_date"])}</span>',
            ref_cell,
        ])
    return f'<div class="section-gap">{card("Statutory UK High Court Case Law XML & SEC EFTS Restructuring Filings (Gap G2 Narrowed)", table(headers, rows), block="court_dockets", count=f"{len(uk)} UK + {len(sec)} SEC", prov="sourced")}</div>'


def thufir_bridge_html(bridge: list[dict[str, Any]] | None, figs: dict[str, Any]) -> str:
    """Render the Upstream Thufir Macro-to-Subterranean Credit Bridge on Tab 0."""
    if not bridge:
        return ""
    items = "".join(
        f'<div class="bridge-item">'
        f'<div class="b-head"><span>{esc(b["thufir_topic"])}</span>{topic_tag(b["target_topic"])}</div>'
        f'<div class="b-macro">{fmt(b["macro_signal"], figs)}</div>'
        f'<div class="b-arrow">▼ Subterranean Credit Transmission</div>'
        f'<div class="b-credit">{fmt(b["credit_channel"], figs)}</div>'
        f'</div>'
        for b in bridge
    )
    inner = f'<div class="bridge-grid">{items}</div>'
    return f'<div class="section-gap">{card("Upstream Thufir Hawat Macro-to-Credit Transmission Bridge", inner, block="thufir_bridge", count=f"{len(bridge)} channels", prov="estimate")}</div>'


def vectors_table_html(c: dict[str, Any], ev: dict[str, Any]) -> str:
    """Render the Consolidated alpha-g StructuredCreditSignalRecord Matrix on Tab 0."""
    vectors = c.get("credit_vectors")
    if not vectors:
        return ""
    ev_hashes = {i["id"]: i.get("sha256", "") for i in ev.get("items", [])}
    headers: list[str | tuple[str, str]] = [
        ("Deal / Cohort ID", "CUSIP, LoanX, or canonical SGC structured credit cohort identifier"),
        ("Topic", "Parent dossier topic tab (click to inspect mechanism)"),
        ("Jurisdiction", "Market jurisdiction: EUR_BSL, US_BSL, UK_WBS, or US_MM_PRIVATE"),
        ("CCC Bucket %", "C_Migration: Percentage of collateral rated CCC+/Caa1 or lower (7.5% standard limit)"),
        ("Jr OC Cushion", "O_Cushion: Basis points above mandatory interest-diversion trip wire"),
        ("WARF", "Moody's/Fitch Weighted Average Rating Factor of the underlying pool"),
        ("WAS (bps)", "Weighted Average Spread of performing loan collateral over benchmark"),
        ("LME Risk [0–1]", "L_Priming: Covenant stripping & unrestricted-subsidiary priming vulnerability index"),
        ("12M Default Est", "Forward 12-month holistic economic default intensity forecast (Legal + LME)"),
        ("Half-Life τ", "Ornstein-Uhlenbeck structural credit signal decay parameter in days"),
        ("alpha-g Gate", "Mandatory execution gate dispatched to alpha-g: ALLOW, WATCH, or HARD_VETO"),
        ("Evidence Seal", "Captured evidence ID and SHA-256 cryptographic hash prefix"),
    ]
    rows = []
    for v in vectors:
        gate = v["action_gate"]
        g_cls = "gate-allow" if gate == "ALLOW" else ("gate-watch" if gate == "WATCH" else "gate-veto")
        ehash = ev_hashes.get(v["evidence"], "")[:10]
        lme = float(v["lme_priming_risk_index"])
        lme_col = "red" if lme >= 0.70 else ("amber" if lme >= 0.35 else "green")
        rows.append([
            f'<span class="mono"><strong>{esc(v["deal_or_loan_id"])}</strong></span>',
            topic_tag(v["topic"]),
            f'<span class="mono">{esc(v["market_jurisdiction"])}</span>',
            f'<span class="mono">{float(v["ccc_bucket_percentage"]):.1f}%</span>',
            f'<span class="mono">{float(v["junior_oc_cushion_bp"]):+.0f} bps</span>',
            f'<span class="mono">{float(v["warf_score"]):.0f}</span>',
            f'<span class="mono">{float(v["was_spread_bp"]):.0f} bps</span>',
            tag(f"{lme:.2f}", lme_col),
            f'<span class="mono">{float(v["default_intensity_forecast"]):.1f}%</span>',
            f'<span class="mono">{float(v["half_life_days"]):.0f}d</span>',
            f'<span class="mono {g_cls}">{esc(gate)}</span>',
            f'{tag(v["evidence"], "green")}<span class="mono muted">{esc(ehash)}…</span>',
        ])
    return f'<div class="section-gap">{card("Downstream alpha-g StructuredCreditSignalRecord Factor Vector & VETO Matrix", table(headers, rows), block="vectors", count=f"{len(rows)} vectors", prov="estimate")}</div>'


def topic_vectors_strip_html(tid: str, c: dict[str, Any], ev: dict[str, Any]) -> str:
    """Render a compact StructuredCreditSignalRecord telemetry strip inside a Topic Tab."""
    vectors = [v for v in (c.get("credit_vectors") or []) if v.get("topic") == tid]
    if not vectors:
        return ""
    ev_hashes = {i["id"]: i.get("sha256", "") for i in ev.get("items", [])}
    strips = []
    for v in vectors:
        gate = v["action_gate"]
        g_cls = "gate-allow" if gate == "ALLOW" else ("gate-watch" if gate == "WATCH" else "gate-veto")
        ehash = ev_hashes.get(v["evidence"], "")[:10]
        strips.append(f"""<div class="vec-strip" data-prov="estimate">
  <div class="vec-cell"><span class="vk">Vector ID ({esc(v["market_jurisdiction"])})</span><span class="vv">{esc(v["deal_or_loan_id"])}</span></div>
  <div class="vec-cell"><span class="vk">CCC Bucket (C_Migration)</span><span class="vv">{float(v["ccc_bucket_percentage"]):.1f}%</span></div>
  <div class="vec-cell"><span class="vk">Junior OC Cushion</span><span class="vv">{float(v["junior_oc_cushion_bp"]):+.0f} bps</span></div>
  <div class="vec-cell"><span class="vk">WARF / WAS</span><span class="vv">{float(v["warf_score"]):.0f} / {float(v["was_spread_bp"]):.0f} bps</span></div>
  <div class="vec-cell"><span class="vk">LME Priming Risk</span><span class="vv">{float(v["lme_priming_risk_index"]):.2f}</span></div>
  <div class="vec-cell"><span class="vk">12M Default / τ</span><span class="vv">{float(v["default_intensity_forecast"]):.1f}% / {float(v["half_life_days"]):.0f}d</span></div>
  <div class="vec-cell"><span class="vk">alpha-g Action Gate</span><span class="vv {g_cls}">{esc(gate)}</span></div>
  <div class="vec-cell"><span class="vk">Evidence Seal ({esc(v["evidence"])})</span><span class="vv mono">{esc(ehash)}…</span></div>
</div>""")
    return "".join(strips)


# ── Tab builders ──────────────────────────────────────────────────────────
def origin_tag(origin: str | None, *, after_exposure: bool = False) -> str:
    """Evidence origin tag (Chrizza-native / Thufir-seeded / telemetry); '—' for legacy captures."""
    if origin not in ORIGINS:
        return '<span class="muted">—</span>'
    label, colour = ORIGINS[origin]
    if origin == "chrizza_native" and after_exposure:
        label = f"{label} · post-Thufir*"
    return tag(label, colour)


def origin_mix_html(ev: dict[str, Any]) -> str:
    """One-line independence census of today's evidence by origin, with post-exposure disclosure."""
    items = ev.get("items", [])
    counts = {k: sum(1 for i in items if i.get("origin") == k) for k in ORIGINS}
    if not any(counts.values()):
        return ""
    post_n = sum(1 for i in items if i.get("origin") == "chrizza_native" and i.get("native_after_exposure"))
    parts = "".join(f'{origin_tag(k)}<span class="mono"> × {counts[k]}</span> ' for k in ORIGINS)
    note = (f' <span class="muted">(* {post_n} captured via open domain queries — verified zero Thufir-seeded '
            'proper nouns/tickers — after reading the upstream Thufir tape)</span>' if post_n else "")
    return f'<p class="small section-gap"><span class="lbl">Evidence independence</span>{parts}{note}</p>'


def freshness_board_html(c: dict[str, Any], prior: dict[str, Any] | None = None,
                         ev: dict[str, Any] | None = None) -> str:
    """Tab 0 day-over-day board: today's topics (NEW / RUNNING), their origin, and stories not carried."""
    topics = [t for t in c["topics"] if t.get("freshness")]
    if not topics:
        return ""
    ev_by_id = {i["id"]: i for i in (ev or {}).get("items", [])}
    headers: list[str | tuple[str, str]] = [
        ("Tab", "Today's topic tab (click to jump)"),
        ("Status", "NEW = news-led story; RUNNING = open situation carried from earlier editions"),
        ("Origin", "Who found the catalyst: Chrizza-native search, Thufir-seeded lead, or sweeper telemetry"),
        ("Thread", "Stable story key carried day over day"),
        ("Open since", "Date the story was first reported"),
        ("Latest catalyst", "Date and type of the newest catalyst (news or market telemetry)"),
        ("Topic", "Today's headline"),
    ]
    rows = []
    for t in topics:
        f = t["freshness"]
        status = tag("🆕 NEW", "green") if f["status"] == "new" else tag("♻️ RUNNING", "amber")
        origins = list(dict.fromkeys(
            (ev_by_id[e].get("origin"), bool(ev_by_id[e].get("native_after_exposure")))
            for e in f.get("catalyst_evidence", []) if e in ev_by_id and ev_by_id[e].get("origin")
        ))
        origin_cell = "".join(origin_tag(o, after_exposure=ae) for o, ae in origins) or origin_tag(None)
        rows.append([topic_tag(t["id"]), status, origin_cell,
                     f'<span class="mono">{esc(f.get("thread", "—"))}</span>',
                     f'<span class="mono">{esc(f["first_reported"])}</span>',
                     f'<span class="mono">{esc(f["latest_catalyst"])}</span> · {esc(f["catalyst_type"])}',
                     esc(t["title"])])
    body = table(headers, rows) + origin_mix_html(ev or {})
    if prior:
        today = {t["freshness"].get("thread") for t in topics}
        dropped = [t for t in prior.get("topics", [])
                   if (t.get("freshness") or {}).get("thread", "") not in today]
        has_threads = any((t.get("freshness") or {}).get("thread") for t in prior.get("topics", []))
        label = ("Stories from the previous edition not carried today (retired or quiet)" if has_threads
                 else "Previous edition topics (published before story threads existed; not carried as threads)")
        if dropped:
            items = "".join(f'<li>{tag("retired", "mauve")} {esc(t.get("title", ""))}</li>' for t in dropped)
            body += (f'<p class="lbl section-gap">{esc(label)} · {esc(prior.get("dossier_id", ""))}</p>'
                     f'<ul class="small">{items}</ul>')
    return f'<div class="section-gap">{card("Topic freshness — day over day", body, count=f"{len(topics)} topics")}</div>'


def brief_tab(c: dict[str, Any], ev: dict[str, Any], quotes_doc: dict[str, Any] | None = None,
              gap_feeds: dict[str, Any] | None = None, prior: dict[str, Any] | None = None) -> str:
    """Tab 0 — the page a CIO reads in ninety seconds."""
    gf = gap_feeds or {}
    figs, b = c["figures"], c["brief"]
    score = figs[b["regime_score_fig"]]
    hero = f"""<div class="hero">
  <div>
    <span class="regime-pill"><span class="pulse-dot"></span>{esc(b["regime_label"])}</span>
    <div class="bluf-label">Bottom line up front {kbadge(BLOCK_PROVENANCE["summary"])}</div>
    <h2 class="hero-headline">{fmt(b["headline"], figs)}</h2>
    <p class="hero-summary">{fmt(b["summary"], figs)}</p>
    {provenance_legend()}
  </div>
  <div class="card gauge-card" data-prov="{esc(score["provenance"])}">
    <h3 class="card-title">Credit regime score {kbadge(score["provenance"])}</h3>
    {gauge_svg(score["value"])}
    <div class="gauge-caption">{esc(score["rationale"])}</div>
  </div>
</div>"""
    pulse = "".join(
        f'<div class="card kpi"><h3 class="card-title">{fmt(p["label"], figs)} {kbadge(figs[p["fig"]]["provenance"])}</h3>'
        f'<div class="kpi-value">{figure_span(p["fig"], figs)}</div><div class="kpi-sub">{fmt(p["sub"], figs)}</div></div>'
        for p in b["pulse"]
    )
    decisions = "".join(
        f'<div class="card decision"><div class="badge">{esc(d["id"])}</div><div>'
        f'<h4>{fmt(d["ask"], figs)}</h4><p><span class="lbl">Why</span>{fmt(d["why"], figs)}</p>'
        f'<p><span class="lbl">Impact</span>{fmt(d["impact"], figs)}</p></div></div>'
        for d in b["decisions"]
    )
    opps = "".join(
        f'<div class="card opp section-gap">{tag(o["id"], "green")}<h4>{fmt(o["label"], figs)}</h4>'
        f'<p>{fmt(o["thesis"], figs)}</p><p><span class="lbl">Why now</span>{fmt(o["why_now"], figs)}</p>'
        f'<p><span class="lbl">Verify</span>{fmt(o["verify"], figs)}</p></div>'
        for o in b["opportunities"]
    )
    vetoes = "".join(
        f'<div class="card veto section-gap">{tag(v["id"], "red")}<h4>{fmt(v["label"], figs)}</h4>'
        f'<p>{fmt(v["rationale"], figs)}</p></div>'
        for v in b["vetoes"]
    )
    calendar = "".join(
        f'<li><div class="when">{esc(e["when"])} · {esc(e["topic"])}</div><div class="event">{fmt(e["event"], figs)}</div>'
        f'<div class="note">{fmt(e["note"], figs)}</div></li>'
        for e in b["calendar"]
    )
    gaps = "".join(f'<li><strong>{esc(g["id"])}</strong> {fmt(g["label"], figs)}</li>' for g in c["gaps"])
    return f"""<section class="tab active" id="tab-0" role="tabpanel" aria-label="Command Brief">
{hero}
<div class="grid grid-4 section-gap">{pulse}</div>
{freshness_board_html(c, prior, ev)}
{proxy_tape_html(quotes_doc)}
{bond_isins_html(gf.get("bond_isins"), c["topics"])}
{nbfi_bdc_html(gf.get("nbfi_bdc"))}
{thufir_bridge_html(b.get("thufir_bridge"), figs)}
<div class="section-gap">{card("Decisions requested of the CIO", f'<div class="grid grid-3">{decisions}</div>', block="decisions", count=f"{len(b['decisions'])} asks")}</div>
<div class="grid grid-2 section-gap">
  {card("Opportunities to anticipate", opps, block="opportunities", count=f"{len(b['opportunities'])}")}
  {card("Hard vetoes", vetoes, block="vetoes", count=f"{len(b['vetoes'])}")}
</div>
{vectors_table_html(c, ev)}
<div class="section-gap">{card("Transmission map", f'<div class="mermaid">{esc(b["mermaid"])}</div>', block="transmission")}</div>
<div class="grid grid-2 section-gap">
  {card("Risk map — topic probability × impact", heatmap_html(c["topics"]) + '<p class="small muted">Ordinal judgement by Chrizza — click any topic tag to open its deep-dive tab.</p>', block="heatmap")}
  {card("Catalyst calendar", f'<ul class="timeline">{calendar}</ul>', block="calendar")}
</div>
<div class="section-gap">{card("Evidence integrity", integrity_html(figs, c["gaps"]) + f'<p class="small section-gap">{kbadge("gap")} Open data gaps — no claim is made on these</p><ul class="small">{gaps}</ul>', block="integrity")}</div>
</section>"""


def freshness_html(t: dict[str, Any], figs: dict[str, Any], ev_doc: dict[str, Any] | None = None) -> str:
    """Topic freshness strip: NEW (news-led) or RUNNING (open since …, with today's delta)."""
    f = t.get("freshness")
    if not f:
        return ""
    if f["status"] == "new":
        badges = tag("🆕 NEW TOPIC", "green") + tag(f'catalyst {f["latest_catalyst"]} · {f["catalyst_type"]}', "cyan")
    else:
        badges = (tag("♻️ RUNNING — NOT CLOSED", "amber") + tag(f'open since {f["first_reported"]}', "mauve")
                  + tag(f'latest {f["latest_catalyst"]} · {f["catalyst_type"]}', "cyan"))
    ev_by_id = {i["id"]: i for i in (ev_doc or {}).get("items", [])}
    origins = list(dict.fromkeys(
        (ev_by_id[e].get("origin"), bool(ev_by_id[e].get("native_after_exposure")))
        for e in f.get("catalyst_evidence", []) if e in ev_by_id and ev_by_id[e].get("origin")
    ))
    badges += "".join(origin_tag(o, after_exposure=ae) for o, ae in origins)
    chips = "".join(tag(e, "cyan") for e in f.get("catalyst_evidence", []))
    delta = (f'<p class="small"><span class="lbl">What is new today</span>{fmt(f["delta"], figs)}</p>'
             if f.get("delta") else "")
    return (f'<div class="evidence-chips section-gap">{badges}<span class="lbl">Catalyst</span>{chips}</div>{delta}')


def topic_tab(index: int, t: dict[str, Any], c: dict[str, Any], ev_doc: dict[str, Any]) -> str:
    """Tabs 1–6 — one topic each, five mandatory sections + optional vector telemetry strip."""
    figs = c["figures"]
    ev = '<span class="lbl">Restated from</span>' + "".join(tag(e, "cyan") for e in t["evidence"])
    gap_tags = "".join(tag(g, "red") for g in t.get("gaps", []))

    def section(n: int, body: str) -> str:
        block = SECTION_BLOCKS[n - 1]
        return (f'<div class="card sec"><div class="sec-head"><span class="sec-n">{n}</span>'
                f'<h3>{SECTION_TITLES[n - 1]}</h3>{kbadge(BLOCK_PROVENANCE[block])}</div>{body}</div>')

    mech = f'<div class="prose"><p>{fmt(t["mechanism"], figs)}</p></div>'
    if t.get("latex"):
        status_text, status_colour, status_key = LATEX_STATUS[t["latex_status"]]
        mech += (f'<p class="section-gap">{tag("FORMULA", "cyan")}{tag(status_text, status_colour)} {kbadge(status_key)}</p>'
                 f'<div class="math">$${html.escape(t["latex"], quote=False)}$$</div>'
                 f'<p class="math-note">{fmt(t["latex_note"], figs)}</p>')
    if t.get("show_stack"):
        mech += stack_html(t, figs)
    factors = '<ul class="factor-list">' + "".join(f"<li>{fmt(f, figs)}</li>" for f in t["factors"]) + "</ul>"
    names = {"A": "Base", "B": "Alternative", "C": "Tail"}
    scen = "".join(
        f'<div class="card scenario {s["id"].lower()}"><div class="sid">{s["id"]} · {names[s["id"]]} — {fmt(s["label"], figs)}</div>'
        f'<div class="p">{est_span(str(s["p"]) + "%", "Scenario " + s["id"] + " probability — Chrizza judgement")}</div>'
        f'<div class="bar"><span style="width: {s["p"]}%"></span></div>'
        f'<div class="prose small">{fmt(s["text"], figs)}</div>'
        + (f'<div class="kill" data-prov="estimate">{kbadge("estimate")} <strong>Kill switch:</strong> {fmt(s["kill_switch"], figs)}</div>'
           if s.get("kill_switch") else "")
        + "</div>"
        for s in t["scenarios"]
    )
    calls = [k for k in c["calls"] if k["topic"] == t["id"]]
    call_rows = "".join(
        f'<li data-prov="estimate"><span class="mono">{esc(k["id"])}</span> · p = {k["p"]:.2f} ({conviction_band(k["p"])}) '
        f'· by {esc(k["resolve_by"])} — {esc(k["proposition"])}</li>'
        for k in calls
    )
    position = (f'<div class="prose"><p><span class="lbl">Posture</span>{fmt(t["posture"], figs)}</p>'
                f'<p><span class="lbl">Verify next</span>{fmt(t["verify"], figs)}</p></div>'
                + (f'<p class="lbl section-gap">Scored calls {kbadge(BLOCK_PROVENANCE["calls"])}</p><ul class="small">{call_rows}</ul>'
                   if calls else "")
                + (f'<p class="small">{kbadge("gap")} Open gaps: {gap_tags}</p>' if gap_tags else ""))
    return f"""<section class="tab" id="tab-{index}" role="tabpanel" aria-label="{esc(t["title"])}">
<div class="card"><div class="topic-head">
  <div class="topic-emoji">{esc(t["emoji"])}</div>
  <div><div class="topic-code">{esc(t["id"])} · TOPIC {index} OF {len(c["topics"])}</div>
    <h2>{fmt(t["title"], figs)}</h2><p class="topic-thesis">{fmt(t["thesis"], figs)}</p>
    <div class="evidence-chips">{ev}</div>{freshness_html(t, figs, ev_doc)}</div>
  <div class="verdict"><span class="v">{fmt(t["verdict"], figs)}</span><span class="s">{fmt(t["stance"], figs)} {kbadge(BLOCK_PROVENANCE["thesis"])}</span></div>
</div>{topic_vectors_strip_html(t["id"], c, ev_doc)}</div>
{section(1, f'<div class="prose"><p>{fmt(t["signal"], figs)}</p></div>')}
{section(2, mech)}
{section(3, factors)}
{section(4, f'<div class="grid grid-3">{scen}</div>')}
{section(5, position)}
</section>"""


def provenance_tab(index: int, c: dict[str, Any], ev: dict[str, Any], ledger: dict[str, Any],
                   registry: dict[str, dict], manifest: list[tuple[str, str]],
                   gap_feeds: dict[str, Any] | None = None) -> str:
    """Last tab — everything a sceptical reader needs to audit the dossier."""
    gf = gap_feeds or {}
    figs = c["figures"]
    st = stats(ledger)
    cap = conviction_cap(st)
    by_id = {k["id"]: k for k in ledger["calls"]}
    calls = table([
        ("Call", "Unique dated forecast identifier in chrizza_call_ledger.json"),
        ("Topic", "Dossier topic tab the forecast belongs to"),
        ("Proposition", "Falsifiable binary market outcome to be verified on resolve_by date"),
        ("p", "Assigned subjective probability in (0, 1)"),
        ("Band", "Conviction tier derived from |p - 0.50|: low (<0.15), medium (<0.30), high (>=0.30)"),
        ("Resolve by", "Mandatory ISO-8601 resolution cut-off date"),
        ("Status", "Ledger status: pending or scored"),
    ], [
        [f'<span class="mono">{esc(k["id"])}</span>', esc(k["topic"]), esc(k["proposition"]), f'{k["p"]:.2f}',
         esc(conviction_band(k["p"])), esc(k["resolve_by"]),
         esc(by_id.get(k["id"], {}).get("status", "unregistered"))] for k in c["calls"]
    ])
    brier = "n/a" if st["brier"] is None else f'{st["brier"]:.3f}'
    hit = "n/a" if st["hit_rate"] is None else f'{100 * st["hit_rate"]:.0f}%'
    ledger_note = (f'<p class="small" data-prov="derived">{kbadge(BLOCK_PROVENANCE["ledger_stats"])} Track record: '
                   f'{st["n_scored"]} scored · hit rate {hit} · Brier {brier} · '
                   f'{st["pending"]} pending → conviction cap <strong>{cap.upper()}</strong>. The cap stays at medium until '
                   'ten calls have been scored.</p>')
    gaps = table([
        ("Gap", "Open intelligence gap identifier"),
        ("Missing", "Data series or primary document not yet available"),
        ("Consequence", "Analytical limitation imposed by this missing input"),
        ("Remedy", "Approved procurement feed or primary filing path to close the gap"),
    ], [
        [esc(g["id"]), fmt(g["label"], figs), fmt(g["impact"], figs), fmt(g["remedy"], figs)] for g in c["gaps"]
    ])
    counts = {p: sum(1 for f in figs.values() if f["provenance"] == p) for p in PROVENANCE}
    filter_bar = (
        '<div class="filter-bar">'
        f'<button type="button" class="filter-btn active" onclick="filterFigures(\'all\', this)">All ({len(figs)})</button>'
        + "".join(
            f'<button type="button" class="filter-btn" onclick="filterFigures(\'{p}\', this)">{p} ({counts[p]})</button>'
            for p in PROVENANCE if counts[p]
        )
        + '<input type="search" id="fig-search-input" class="filter-search" placeholder="Filter figures by ID, label, or evidence…" oninput="filterFigures()">'
        '</div>'
    )
    fig_rows = filter_bar + table([
        ("ID", "Figure token identifier referenced in dossier prose"),
        ("Figure", "Quantitative metric description and context"),
        ("Value", "Formatted display value with hover audit trail"),
        ("Key", "Provenance classification: sourced, derived, estimate, or illustrative"),
        ("Confidence", "Evidentiary confidence level: high, medium, or low"),
        ("As of", "Point-in-time observation or cut-off date"),
        ("Basis", "Sealed evidence capture ID, derivation formula, or estimate rationale"),
    ], [
        [f'<span class="mono">{esc(fid)}</span>', esc(f["label"]), figure_span(fid, figs), kbadge(f["provenance"]),
         esc(f["confidence"]), esc(f.get("as_of", "—")),
         esc(f.get("evidence") or f.get("rationale") or ", ".join(f.get("inputs", [])))] for fid, f in figs.items()
    ], table_id="fig-register-tbl", row_attrs=[f'data-fig-prov="{esc(f["provenance"])}" data-prov="{esc(f["provenance"])}"' for f in figs.values()])
    ev_rows = table([
        ("ID", "Evidence capture identifier referenced by sourced figures"),
        ("Origin", "Who found the story: Chrizza-native search, Thufir-seeded lead, or sweeper telemetry"),
        ("Capture", "Capture title, expandable verbatim note, and search query"),
        ("Publishers", "Originating Tier 1–4 credit desks, rating agencies, or dockets"),
        ("Captured (UTC)", "Exact UTC timestamp of intelligence harvest"),
        ("Seal", "SHA-256 hex digest of the verbatim capture excerpt"),
    ], [
        [f'<span class="mono">{esc(i["id"])}</span>',
         origin_tag(i.get("origin"), after_exposure=bool(i.get("native_after_exposure"))),
         f'<strong>{esc(i["title"])}</strong><details><summary>Capture note</summary><p>{esc(i["excerpt"])}</p>'
         f'<p class="mono muted">query: {esc(i["query"])}</p></details>',
         esc(", ".join(i["publisher_domains"])), esc(i["captured_at_utc"]),
         f'<span class="mono" title="{esc(i["sha256"])}">{esc(i["sha256"][:12])}…</span>'] for i in ev["items"]
    ])
    bib_rows = []
    for b in c["bibliography"]:
        if b.get("candidate"):
            bib_rows.append([tag("CANDIDATE", "amber"), esc(b["domain"]), "—", fmt(b["used_for"], figs)])
        else:
            r = registry[b["source_id"]]
            bib_rows.append([tag(f'TIER {r["tier"]}', "green"), esc(f'{r["name"]} ({r["domain"]})'),
                             esc(r.get("reliability_rating", "—")), fmt(b["used_for"], figs)])
    bib = table([
        ("Status", "Registry tier in structured_credit_intelligence_sources.json or candidate status"),
        ("Source", "Specialist credit desk, rating agency, trustee, or central bank"),
        ("Rating", "Empirical reliability rating in the SGC registry"),
        ("Used for", "Specific topics and evidence captures substantiated in this cycle"),
    ], bib_rows)
    heur = '<ul class="factor-list">' + "".join(
        f'<li><strong>{esc(h["id"])}</strong> {fmt(h["text"], figs)}</li>' for h in c["heuristics"]) + "</ul>"
    man = table([
        ("Artefact", "Workspace-relative path of the pipeline input or script"),
        ("SHA-256", "Full 64-hex-character SHA-256 cryptographic digest at render time"),
    ], [[esc(n), f'<span class="mono-hash">{esc(h)}</span>'] for n, h in manifest])
    method = (f'<p class="small">{esc(ev.get("method_note", ""))}</p>'
              '<p class="small muted">Every figure in this dossier is a registered object with provenance. '
              'Sourced figures cite a sealed capture note; estimates carry a rationale; nothing numeric enters '
              'the prose except through the figure register.</p>')
    return f"""<section class="tab" id="tab-{index}" role="tabpanel" aria-label="Provenance and Ledger">
<div class="grid grid-2">
  {card("Evidence integrity", integrity_html(figs, c["gaps"]) + method, block="integrity")}
  {card("Analyst heuristics carried forward", heur, block="heuristics")}
</div>
<div class="section-gap">{card("Call ledger — the OODA reflect loop", ledger_note + f'<div data-prov="estimate">{calls}</div>', block="calls")}</div>
{clo_tranches_html(gf.get("clo_tranches"))}
{court_dockets_html(gf.get("court_dockets"))}
<div class="section-gap">{card("Data gap register", gaps, key="gap", count=str(len(c["gaps"])))}</div>
<div class="section-gap">{card("Figure register — every number and its key", fig_rows, count=str(len(figs)))}</div>
<div class="section-gap">{card("Evidence capture notes (sealed)", ev_rows, block="evidence_notes", prov="sourced", count=str(len(ev["items"])))}</div>
<div class="section-gap">{card("Bibliography — source registry", bib, block="bibliography")}</div>
<div class="section-gap">{card("Build manifest", man, block="manifest", prov="derived")}</div>
</section>"""


# ── Assembly ──────────────────────────────────────────────────────────────
def load_gap_feeds(stamp: str) -> dict[str, Any]:
    """Load any sealed v4 Data Gap telemetry files available for a session stamp."""
    mapping = {
        "nbfi_bdc": nbfi_bdc_path(stamp),
        "clo_tranches": clo_tranches_path(stamp),
        "court_dockets": court_dockets_path(stamp),
        "bond_isins": bond_isins_path(stamp),
    }
    return {key: load_json(p) for key, p in mapping.items() if p.exists()}


def build_manifest(stamp: str) -> list[tuple[str, str]]:
    """SHA-256 of every input that shaped this render."""
    files = [content_path(stamp), evidence_path(stamp)]
    for opt_path in (
        quotes_path(stamp),
        nbfi_bdc_path(stamp),
        bond_isins_path(stamp),
        clo_tranches_path(stamp),
        court_dockets_path(stamp),
        vectors_path(stamp),
    ):
        if opt_path.exists():
            files.append(opt_path)
    if WATCHLIST_PATH.exists():
        files.append(WATCHLIST_PATH)
    files += [
        LEDGER_PATH,
        MIRROR_TEMPLATE,
        HERE / "ops_chrizza_generate_credit_dossier.py",
        HERE / "ops_chrizza_pre_publish_guard.py",
        HERE / "ops_chrizza_content_builder.py",
        HERE / "ops_chrizza_learning_ledger.py",
        HERE / "ops_chrizza_dossier_common.py",
        HERE / "ops_chrizza_sweep_nbfi_and_bdc.py",
        HERE / "ops_chrizza_sweep_bond_isins.py",
        HERE / "ops_chrizza_sweep_clo_nport.py",
        HERE / "ops_chrizza_sweep_court_dockets.py",
    ]
    return [(p.relative_to(ROOT).as_posix(), sha256_file(p)) for p in files if p.exists()]


def emit_vectors_file(stamp: str, c: dict[str, Any], ev: dict[str, Any]) -> Path | None:
    """Emit standalone SHA-256-sealed StructuredCreditSignalRecord JSON for alpha-g when vectors exist."""
    vectors = c.get("credit_vectors")
    if not vectors:
        return None
    ev_hashes = {i["id"]: i.get("sha256", "") for i in ev.get("items", [])}
    records = []
    for v in vectors:
        records.append({
            "deal_or_loan_id": v["deal_or_loan_id"],
            "timestamp_utc": c["observed_at_utc"],
            "topic": v["topic"],
            "market_jurisdiction": v["market_jurisdiction"],
            "ccc_bucket_percentage": float(v["ccc_bucket_percentage"]),
            "junior_oc_cushion_bp": float(v["junior_oc_cushion_bp"]),
            "warf_score": float(v["warf_score"]),
            "was_spread_bp": float(v["was_spread_bp"]),
            "lme_priming_risk_index": float(v["lme_priming_risk_index"]),
            "equity_nav_mark": float(v.get("equity_nav_mark", 0.0)),
            "default_intensity_forecast": float(v["default_intensity_forecast"]),
            "half_life_days": float(v["half_life_days"]),
            "action_gate": v["action_gate"],
            "evidence_id": v["evidence"],
            "evidence_hash": ev_hashes.get(v["evidence"], ""),
        })
    payload: dict[str, Any] = {
        "schema": SCHEMA_VECTORS,
        "dossier_id": c["dossier_id"],
        "observed_at_utc": c["observed_at_utc"],
        "producer": "Chrizza (structured-credit-agent)",
        "consumer": "alpha-g (quant-research-agent)",
        "records": records,
    }
    payload["sha256"] = seal_payload(payload)
    vpath = vectors_path(stamp)
    save_json(vpath, payload)
    return vpath


def short_tab_title(t: dict[str, Any], max_chars: int = 28) -> str:
    """Return a concise tab title without ever slicing a word mid-character."""
    explicit = str(t.get("short_title") or "").strip()
    if explicit:
        return explicit
    title = str(t.get("title") or "").strip()
    if len(title) <= max_chars:
        return title
    cut = title[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:-—–")
    return cut or title[:max_chars]


def render_html(c: dict[str, Any], ev: dict[str, Any], ledger: dict[str, Any], registry: dict[str, dict],
                template: str, manifest: list[tuple[str, str]],
                quotes_doc: dict[str, Any] | None = None,
                gap_feeds: dict[str, Any] | None = None,
                prior: dict[str, Any] | None = None) -> str:
    """Fill the template slots. Pure function: no file I/O (prior = previous edition, for the freshness board)."""
    observed = parse_utc(c["observed_at_utc"])
    st = stats(ledger)
    labels = [TAB_LABELS[0]] + [f'{t["emoji"]} {t["id"]}: {short_tab_title(t)}' for t in c["topics"]] + [TAB_LABELS[7]]
    last = len(labels) - 1
    nav = "\n".join(
        f'<button class="tab-btn{" active" if i == 0 else ""}" role="tab" aria-selected="{"true" if i == 0 else "false"}" '
        f'data-tab="tab-{i}" data-key="{i}" onclick="switchTab(\'tab-{i}\', this)"><span class="k">{i}</span>{esc(label)}</button>'
        for i, label in enumerate(labels)
    )
    sections = [brief_tab(c, ev, quotes_doc, gap_feeds, prior)] + [topic_tab(i + 1, t, c, ev) for i, t in enumerate(c["topics"])]
    sections.append(provenance_tab(last, c, ev, ledger, registry, manifest, gap_feeds))
    footer = (f'<p><strong>{esc(c["dossier_id"])}</strong> · {esc(c["author"])} · for {esc(c["audience"])} · '
              f'observed {esc(c["observed_at_utc"])} · session {esc(c["session_for"])}</p>'
              '<p>Rendered by roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py (v4) · content & HTML guard passed at render · '
              'UNLOCKED — awaiting Agent Manager ratification.</p>'
              f'<p class="creed">“{esc(CREED)}” — the old is different, but the new is beautiful.</p>')
    slots = {
        "PAGE_TITLE": esc(c["title"]),
        "INFINIX_SVG": infinix_svg(),
        "SGC_SVG": sgc_svg(),
        "PIT_VAL": esc(f'Observed {observed:%d %b %Y %H:%M}Z · for {c["session_for"]} session'),
        "EVIDENCE_VAL": esc(f'{len(ev["items"])} sealed captures · {len(c["figures"])} figures · {len(c["gaps"])} gaps'),
        "LEDGER_VAL": esc(f'Ledger {st["n_scored"]} scored · {st["pending"]} pending · cap {conviction_cap(st).upper()}'),
        "NAV_TABS": nav,
        "TAB_SECTIONS": "\n".join(sections),
        "FOOTER_META": footer,
    }
    out = SLOT_RE.sub(lambda m: slots[m.group(0)[2:-2]], template)
    return out


# ── Commands ──────────────────────────────────────────────────────────────
def cmd_seal(stamp: str) -> int:
    """Seal every evidence excerpt with sha256(excerpt)."""
    path = evidence_path(stamp)
    ev = load_json(path)
    for item in ev["items"]:
        item["sha256"] = sha256_text(item["excerpt"])
    ev["sealed_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(path, ev)
    print(f"sealed {len(ev['items'])} evidence item(s) in {path.relative_to(ROOT).as_posix()}")
    return 0


def cmd_sweep_quotes(stamp: str) -> int:
    """Sweep live FMP quotes for CREDIT_PROXY_SYMBOLS + US Treasury curve and seal to disk."""
    sys.path.insert(0, str(ROOT / "roc" / "scripts" / "ops_thufir"))
    from ops_thufir_validate_fmp_symbology import load_fmp_api_key  # noqa: E402

    api_key = load_fmp_api_key()
    if not api_key:
        raise RuntimeError("FMP API key not found in sgc/config/credentials.toml")
    syms = ",".join(CREDIT_PROXY_SYMBOLS)
    q_url = f"{FMP_BASE}/batch-quote?symbols={urllib.parse.quote(syms)}&apikey={api_key}"
    quotes: dict[str, Any] = {}
    with urllib.request.urlopen(q_url, timeout=20) as resp:
        raw_list = json.loads(resp.read().decode("utf-8")) or []
    for q in raw_list:
        sym = q.get("symbol")
        if not sym:
            continue
        px = float(q.get("price") or 0.0)
        avg50 = float(q.get("priceAvg50") or 0.0)
        avg200 = float(q.get("priceAvg200") or 0.0)
        yr_high = float(q.get("yearHigh") or 0.0)
        yr_low = float(q.get("yearLow") or 0.0)
        quotes[sym] = {
            "symbol": sym,
            "name": q.get("name", sym),
            "price": round(px, 4),
            "changePercentage": round(float(q.get("changePercentage") or 0.0), 4),
            "priceAvg50": round(avg50, 4),
            "priceAvg200": round(avg200, 4),
            "yearHigh": round(yr_high, 4),
            "yearLow": round(yr_low, 4),
            "delta50Pct": round(100.0 * (px - avg50) / avg50, 2) if avg50 > 0 else None,
            "delta200Pct": round(100.0 * (px - avg200) / avg200, 2) if avg200 > 0 else None,
            "drawdownHighPct": round(100.0 * (px - yr_high) / yr_high, 2) if yr_high > 0 else None,
            "timestamp": q.get("timestamp"),
        }
    tsy_latest: dict[str, Any] = {}
    try:
        t_url = f"{FMP_BASE}/treasury-rates?apikey={api_key}"
        with urllib.request.urlopen(t_url, timeout=15) as resp:
            t_list = json.loads(resp.read().decode("utf-8")) or []
        if t_list:
            top = t_list[0]
            tsy_latest = {
                "date": top.get("date"),
                "month3": top.get("month3"),
                "year2": top.get("year2"),
                "year5": top.get("year5"),
                "year10": top.get("year10"),
                "year30": top.get("year30"),
            }
    except Exception:  # noqa: BLE001
        tsy_latest = {}

    payload: dict[str, Any] = {
        "schema": SCHEMA_QUOTES,
        "date": stamp,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "FMP stable batch-quote & treasury-rates",
        "quotes": quotes,
        "treasury": tsy_latest,
    }
    payload["sha256"] = seal_payload(payload)
    path = quotes_path(stamp)
    save_json(path, payload)
    print(f"swept & sealed {len(quotes)} credit proxy quote(s) in {path.relative_to(ROOT).as_posix()} sha256={payload['sha256'][:16]}…")
    return 0


def cmd_sweep_gaps(stamp: str) -> int:
    """Execute all four deterministic Data Gap Registry sweepers (G1, G2, G4+G3, G5)."""
    from ops_chrizza_sweep_bond_isins import sweep_bond_isins  # noqa: E402
    from ops_chrizza_sweep_clo_nport import sweep_clo_nport  # noqa: E402
    from ops_chrizza_sweep_court_dockets import sweep_court_dockets  # noqa: E402
    from ops_chrizza_sweep_nbfi_and_bdc import sweep_nbfi_and_bdc  # noqa: E402

    sweep_nbfi_and_bdc(stamp)
    sweep_bond_isins(stamp)
    sweep_clo_nport(stamp)
    sweep_court_dockets(stamp)
    return 0


def cmd_sweep_all(stamp: str) -> int:
    """Execute FMP proxy quotes + all four Data Gap Registry sweepers."""
    cmd_sweep_quotes(stamp)
    cmd_sweep_gaps(stamp)
    return 0


def cmd_sync_template() -> int:
    """Copy the canonical template to the runtime mirror."""
    MIRROR_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CANONICAL_TEMPLATE, MIRROR_TEMPLATE)
    print(f"mirror synced: {sha256_file(MIRROR_TEMPLATE)}")
    return 0


def cmd_render(stamp: str) -> int:
    """Guard the content, emit vectors, then render and verify the dossier HTML."""
    c, ev = load_json(content_path(stamp)), load_json(evidence_path(stamp))
    ledger, registry = load_ledger(), load_registry()
    q_path = quotes_path(stamp)
    quotes_doc = load_json(q_path) if q_path.exists() else None
    gap_feeds = load_gap_feeds(stamp)
    defects = check_template_sync() + check_evidence(ev)
    if quotes_doc is not None:
        defects += check_quotes(quotes_doc)
    defects += check_gap_feeds(stamp)
    prior = prior_content(stamp)
    defects += check_content(c, ev, registry, ledger, prior)
    if defects:
        for d in defects:
            print(f"  ✗ {d}")
        print(f"REFUSED — {len(defects)} content defect(s); fix the content, not the guard")
        return 1
    vpath = emit_vectors_file(stamp, c, ev)
    if vpath:
        print(f"emitted {len(c['credit_vectors'])} credit vector(s) to {vpath.relative_to(ROOT).as_posix()}")
    out = render_html(c, ev, ledger, registry, MIRROR_TEMPLATE.read_text(encoding="utf-8"),
                      build_manifest(stamp), quotes_doc, gap_feeds, prior)
    html_defects = check_html(out)
    if html_defects:
        for d in html_defects:
            print(f"  ✗ {d}")
        print(f"REFUSED — {len(html_defects)} HTML defect(s)")
        return 1
    path = output_path(stamp)
    path.write_text(out, encoding="utf-8")
    print(f"rendered {path.relative_to(ROOT).as_posix()} ({len(out):,} chars) sha256={sha256_file(path)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("seal", "sweep-quotes", "sweep-gaps", "sweep-all", "render"):
        sp = sub.add_parser(name)
        sp.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    sub.add_parser("sync-template")
    args = parser.parse_args(argv)
    if args.cmd == "seal":
        return cmd_seal(args.date)
    if args.cmd == "sweep-quotes":
        return cmd_sweep_quotes(args.date)
    if args.cmd == "sweep-gaps":
        return cmd_sweep_gaps(args.date)
    if args.cmd == "sweep-all":
        return cmd_sweep_all(args.date)
    if args.cmd == "render":
        return cmd_render(args.date)
    return cmd_sync_template()


if __name__ == "__main__":
    raise SystemExit(main())
