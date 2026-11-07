---
description: Chrizza's Canonical Structured Credit & CLO Horizon Dossier Report HTML Visualizer Workflow
---

# Operate Chrizza Structured Credit & CLO Horizon Dossier Report

> **RAD\*ICAL Control:** 🦅💎 Hawk Diamond | **RC:** 🦋 RC-Butterfly | **Author:** Chrizza (Master of Structured Credit & Debt Forensics)  
> **Hardened Canonical Master Template:** [`DOCS/4_operate/templates/Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html`](DOCS/4_operate/templates/Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html) (Hawk Diamond 🦅💎 | Runtime Mirror: `roc/scripts/ops_chrizza/templates/Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html`)  
> **Core Pipeline Engine:** [`roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py`](roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py)  
> **v4 Data-Gap Sweepers (`sweep-gaps` / `sweep-all`):**  
> - `G5` Eurobond & UK WBS ISIN Order Books: [`roc/scripts/ops_chrizza/ops_chrizza_sweep_bond_isins.py`](roc/scripts/ops_chrizza/ops_chrizza_sweep_bond_isins.py)  
> - `G4` + `G3` Fed H.8 NDFI, Credit OAS & SEC EDGAR BDC `10-Q` XBRL PIK: [`roc/scripts/ops_chrizza/ops_chrizza_sweep_nbfi_and_bdc.py`](roc/scripts/ops_chrizza/ops_chrizza_sweep_nbfi_and_bdc.py)  
> - `G1` SEC EDGAR Form `NPORT-P` Deal-Level CLO Tranches + Trustee Inbox: [`roc/scripts/ops_chrizza/ops_chrizza_sweep_clo_nport.py`](roc/scripts/ops_chrizza/ops_chrizza_sweep_clo_nport.py)  
> - `G2` UK High Court Case Law XML, SEC EFTS Filings + Docket PDF Inbox: [`roc/scripts/ops_chrizza/ops_chrizza_sweep_court_dockets.py`](roc/scripts/ops_chrizza/ops_chrizza_sweep_court_dockets.py)  
> **Fail-Closed Content Guard:** [`roc/scripts/ops_chrizza/ops_chrizza_pre_publish_guard.py`](roc/scripts/ops_chrizza/ops_chrizza_pre_publish_guard.py)  
> **Incremental Chunk Builder & Assembler (v5):** [`roc/scripts/ops_chrizza/ops_chrizza_content_builder.py`](roc/scripts/ops_chrizza/ops_chrizza_content_builder.py) (`split`, `check-chunk`, `assemble` under `roc/scripts/ops_chrizza/content/fragments/<YYYYMMDD>/`)  
> **Learning & Call Ledger:** [`roc/scripts/ops_chrizza/ops_chrizza_learning_ledger.py`](roc/scripts/ops_chrizza/ops_chrizza_learning_ledger.py) & [`roc/scripts/ops_chrizza/chrizza_call_ledger.json`](roc/scripts/ops_chrizza/chrizza_call_ledger.json)  
> **Intelligence Source Registry & ISIN Watchlist:** [`roc/config/structured_credit_intelligence_sources.json`](roc/config/structured_credit_intelligence_sources.json) & [`roc/config/structured_credit_isin_watchlist.json`](roc/config/structured_credit_isin_watchlist.json)  
> **Active Memory:** [`.agent/skills/structured-credit-agent/MEM-JOG-Chrizza-Structured-Credit-And-CLO-Forensics-Bible.md`](.agent/skills/structured-credit-agent/MEM-JOG-Chrizza-Structured-Credit-And-CLO-Forensics-Bible.md)
> **v5 Topic Freshness Contract (2026-11-07, Agent Manager authorised edit of this 💎 file):** topics are selected from *current* news flow every day, never from the watch-list or from habit. Enforced fail-closed by `check_freshness` in the guard (see §4.3).

---

## 1. Purpose & Operational Mandate

This workflow defines the mandatory, deterministic Start of Day (SOD) intelligence cycle for **Chrizza** (`structured-credit-agent`), Master of Structured Credit & Debt Forensics.

Every structured credit horizon sweep, leveraged loan covenant autopsy, European & US CLO capital structure evaluation, CCC bucket migration study, Overcollateralization (OC) cliff test, and Liability Management Exercise (LME) dossier authored by Chrizza MUST conform to this pipeline.

### The Alexandrian Creed
```text
"O paliós eínai alliós, allá o néos eínai oraíos."
(The old way has its timeless character, but the new is dynamic and handsome.)

Seniority is written in indentures; recovery is forged in the waterfall;
par is a temporary illusion until the cash flows speak.
```

### Inviolable Separation of Concerns (v4 Enhanced Pipeline)
The pipeline strictly enforces a 7-way separation of concerns so that **intelligence is never contaminated by presentation**, and **presentation never invents intelligence**:
1. **Live Market Proxy Quotes JSON (`evidence/credit_quotes_<date>.json`):** Live FMP batch quotes for 10 structured credit, senior loan, and public BDC equity proxies (`JAAA`, `JBBB`, `CLOI`, `BKLN`, `SRLN`, `HYG`, `LQD`, `ARCC`, `OBDC`, `BXSL`) plus the US Treasury yield curve (`3M`–`30Y`), swept via `sweep-quotes` / `sweep-all` and sealed with `sha256` (**Observe — Live Proxy Tape**).
2. **Statutory & Exchange Data-Gap Telemetry JSONs (`evidence/credit_bond_isins_<date>.json`, `evidence/credit_nbfi_bdc_<date>.json`, `evidence/credit_clo_tranches_<date>.json`, `evidence/credit_court_dockets_<date>.json`):** Four deterministic, SHA-256-sealed statutory and exchange feeds swept via `sweep-gaps` / `sweep-all` covering Stuttgart/Frankfurt Eurobond & UK WBS ISIN order books (`Gap G5`), FRED H.8 bank-to-NDFI lending + ICE BofA OAS + SEC EDGAR BDC Form `10-Q` XBRL PIK Debt Interest vs PIK Preferred Dividend decomposition (`Gaps G3 & G4`), SEC EDGAR Form `NPORT-P` deal-level CLO tranche holdings + `inbox/trustee/` drop-ins (`Gap G1`), and UK National Archives High Court Case Law XML + SEC EFTS restructuring filings + `inbox/dockets/` local PDF seals (`Gap G2`) (**Observe — Statutory & Exchange Telemetry**).
3. **Evidence JSON (`evidence/credit_evidence_<date>.json`):** Dated capture notes from Tier 1–4 registered sources, sealed with `sha256(excerpt)` (**Observe — Forensic Notes**).
4. **Content JSON (`content/credit_content_<date>.json`):** Structured analytical figures registry (`[[Fxx]]` tokens supporting 2- and 3-digit IDs `F01`–`F999`), upstream `thufir_bridge`, machine-readable `credit_vectors`, 5 mandatory sections per topic tab, explicit LaTeX formulas with honest status badges, 3-scenario forward trees summing to 100%, and CIO decisions (**Orient & Decide**).
5. **Emitted Alpha-G Vectors JSON (`vectors/credit_vectors_<date>.json`):** Standalone, SHA-256-sealed `StructuredCreditSignalRecord` payload emitted automatically during `render` for downstream consumption by `alpha-g` (**Handoff**).
6. **Call Ledger JSON (`chrizza_call_ledger.json`):** Scored, falsifiable track record that dynamically caps analyst conviction via Brier score calibration (**Reflect**).
7. **HTML Template (`Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html`):** Content-free HTML shell equipped with interactive client-side analytical tools (Interactive CLO 2.0 Waterfall & Subordination Stress Simulator, clickable Topic Jump pills, direct statutory EDGAR/High Court links, Tab 7 Interactive Figure Filter & Search, and institutional `<th>` hover tooltips). The template carries zero hardcoded intelligence; every figure is injected deterministically from the sealed JSON payloads (**Act**).

### Surveillance Universe ≠ Topic Selection (v5)
- `roc/config/structured_credit_isin_watchlist.json` defines **what is monitored** (ISINs grouped into neutral `themes`, e.g. `thames_water_wbs`, `uk_eu_cable_telecom`, `drahi_altice`). It never chooses a topic and carries **no topic IDs**.
- Sweepers and the renderer contain **no issuer or topic literals**: bond-tape pills are computed per theme from the sealed quotes, and a bond links to a topic tab only when one of *today's* topics claims its theme via `watch_themes`. Unclaimed themes render as a muted `watch-list` tag (surveillance only).
- Topics are chosen in Step 1 from the day's news captures; each carries a stable story `thread` so the dossier shows, day over day, what is new, what is still running and what has gone quiet.

---

## 2. 🏛️ The Primary HTML Architecture & Tab Hierarchy

Every generated credit dossier report MUST contain an 8-tab structure:
1. **Tab 0:** `Command Brief` — 90-second CIO cockpit.
2. **Tabs 1–6:** `T1` through `T6` — Dedicated thematic structured credit topic tabs, **selected fresh each day from current news flow** (badged 🆕 NEW or ♻️ RUNNING). The headlines in the diagram below are historical examples only — never a fixed line-up.
3. **Tab 7:** `Provenance & Ledger` — Complete cryptographic audit trail, figures register, sealed evidence notes, source bibliography, heuristics, and build manifest.

```text
+----------------------------------------------------------------------------------------------------+
|               STRUCTURED CREDIT & CLO HORIZON DOSSIER — DD MMM YYYY                                |
+----------------------------------------------------------------------------------------------------+
| Masthead: Infinix Brand SVG ➔ Title & Kicker ➔ Meta Chips (PIT, Evidence, Ledger) ➔ SGC Brand SVG  |
+----------------------------------------------------------------------------------------------------+
| Classification Banner: For CIO · Muad'Dib · Agent Manager — research intelligence, not advice       |
+----------------------------------------------------------------------------------------------------+
| Tab 0: 0 Command Brief (Hero, Gauge, 4 KPIs, 3 CIO Asks, Opportunities, Vetoes, Heatmap, Flowchart)|
| Tab 1: 1 💶 T1: [Topic 1 Headline — e.g. CLO Liabilities vs Arbitrage]                             |
| Tab 2: 2 ⚡ T2: [Topic 2 Headline — e.g. Altice International LME Battlefield]                     |
| Tab 3: 3 🏛️ T3: [Topic 3 Headline — e.g. Thames Water Junior WBS Recovery]                         |
| Tab 4: 4 📉 T4: [Topic 4 Headline — e.g. Default Cycle & Fitch Concern List]                       |
| Tab 5: 5 ⚔️ T5: [Topic 5 Headline — e.g. Private Credit 'Bad PIK' Shadow Defaults]                 |
| Tab 6: 6 🏦 T6: [Topic 6 Headline — e.g. Layered Leverage & AI Capex Debt Contagion]               |
| Tab 7: 7 Provenance & Ledger (Integrity Bar, Call Ledger, Gaps, Figures, Evidence, Bibliography)   |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. 📋 Detailed Tab Blueprint & Structural Invariants

### 3.1 Masthead & Header Geometry (Sticky Blur & Brand SVGs)
The sticky masthead (`backdrop-filter: blur(14px); background: rgba(6, 10, 20, 0.82);`) pins the master controls and tab links to the top of the viewport during vertical scrolling:
- **Infinix Official SVG:** Reused directly via `infinix_svg()` from `sgc/crates/sgc-app/ui/src/assets/infinix-brand-logo.svg` (`width="52" height="26"`).
- **Brand Title:**
  - Kicker: `Selective Gradient Capital · Chrizza Credit Forensics` (`font-size: 11px; letter-spacing: 1.6px; text-transform: uppercase; color: var(--mute);`).
  - H1 Title: `Structured Credit & CLO Horizon Dossier — <DD MMM YYYY>` rendered with metallic gradient (`linear-gradient(90deg, var(--gold-2), var(--gold) 45%, var(--mauve-2))`).
- **Right Meta Strip (3 Unified Chips):**
  - `⏱ PIT_VAL`: Point-in-time observation timestamp and session window (e.g. `Observed 26 Oct 2026 07:00Z · for London/NY cash session`).
  - `🔏 EVIDENCE_VAL`: Evidence and gap census (e.g. `10 sealed captures · 41 figures · 5 gaps`).
  - `🎯 LEDGER_VAL`: Active track record and current conviction ceiling (e.g. `Ledger 0 scored · 5 pending · cap MEDIUM`).
- **SGC Official SVG:** Reused directly via `sgc_svg()` from `sgc/crates/sgc-app/ui/src/app/sgc-top-status-bar.ts` (`width="34" height="30"`, white `#ffffff` background, navy `#003b70` `SG`, gold `#D4A843` `<tspan>C</tspan>`, and mauve `#8B6B99` underline bar).
- **Classification Strip:** `For CIO · Muad'Dib · Agent Manager — research intelligence, not investment advice` (`letter-spacing: 2.4px; text-transform: uppercase; color: var(--mauve-2);`).

---

### 3.2 Tab 0 — The Command Brief (90-Second CIO Cockpit)
Tab 0 synthesizes the entire operational environment for executive consumption:

1. **Hero Banner:**
   - **Regime Pill:** Pulsing red/amber dot (`.pulse-dot`) + uppercase regime designation (e.g. `LIABILITY-RICH · COLLATERAL-POOR · DEFAULTS RISING`).
   - **BLUF (Bottom Line Up Front):** Label stamped with `estimate` kbadge + bold high-impact headline + crisp summary prose with embedded `[[Fxx]]` figure tokens.
   - **Front-Page Provenance Legend:** Interactive color chips explaining the four figure keys (`sourced`, `derived`, `estimate`, `illustrative`) and the `gap` non-claim marker.
   - **Credit Regime Gauge SVG:** Semicircular vector gauge spanning from $-100$ (Extreme Risk-Off, crimson) through $0$ (Neutral, amber) to $+100$ (Risk-On, emerald), displaying the dynamic needle angle, composite score, and concise Mentat rationale.
2. **KPI Pulse Strip (4 Glass Cards):**
   - Four vital credit metrics featuring responsive headline values (`clamp(20px, 1.85vw, 28px); font-weight: 800`), provenance badges, and subtext context (e.g. US BB spread widening, European telecom TLB fire sale, NY Commercial Division lawsuit, Fitch BDC PIK share).
   - **Hard Anti-Overspill Rules (enforced by `ops_chrizza_pre_publish_guard.py`):**
     * Each pulse card `label` (`PULSE_LABEL_MAX_CHARS`) MUST be $\le 28$ characters so the header never collides with its `.kbadge`.
     * Each pulse card's referenced figure `display` (`PULSE_VALUE_MAX_CHARS`) MUST be $\le 16$ characters and MUST NOT contain parenthetical `(...)` or semicolon `;` subtext (keep the hero `.kpi-value` a crisp metric like `"$500m"`, `"15.65% PIK"`, `"50.36 pts"`, `"3.51% OAS"` and place all supporting context in `pulse.sub`).
     * Every figure's inline `display` string across the entire `figures` dictionary (`FIGURE_DISPLAY_MAX_CHARS`) MUST be $\le 34$ characters (detailed explanations belong in `label`, which renders in hover tooltips and the Tab 7 Figure Register).
2b. **Topic Freshness Board — Day over Day (`freshness_board_html`, v5):**
   - Table of today's six topics: jump pill, 🆕 NEW / ♻️ RUNNING badge, story `thread`, open-since date, latest catalyst date and type (`news` / `telemetry`), and headline.
   - Below it, the stories from the previous edition **not carried today** (tagged `retired`), so the CIO sees what has gone quiet rather than silently losing it. Editions published before threads existed are listed as "previous edition topics".
3. **Liquid Structured Credit, Senior Loan & BDC Proxy Tape (`proxy_tape_html`):**
   - US Treasury Curve Anchor bar (`3M`, `2Y`, `5Y`, `10Y`, `30Y`, and `2s10s` slope) + 10-instrument institutional table (`JAAA`, `JBBB`, `CLOI`, `BKLN`, `SRLN`, `HYG`, `LQD`, `ARCC`, `OBDC`, `BXSL`) with 1D change, 50D/200D MA deltas, 52-week range, and drawdown from 52W high. Every `<th>` carries an institutional hover tooltip (`.th-tip`).
4. **Benchmark Eurobond & UK WBS ISIN Order-Book Tape (`bond_isins_html` — Gap `G5`):**
   - Sealed Stuttgart & Frankfurt exchange two-sided clean bid-ask-mid quotes, bid-ask spread, 52-week high, and 1-year drawdown across the benchmark Eurobond/Reg S ISINs in the watchlist, with per-**theme** average-mid pills computed from the quotes (no issuer literals). The Topic column shows a jump pill only when a current topic claims the bond's theme via `watch_themes`; otherwise a muted `watch-list` tag.
5. **Statutory Fed H.8 Bank-to-NDFI Lending, Credit OAS & SEC EDGAR BDC XBRL PIK Monitor (`nbfi_bdc_html` — Gaps `G3` & `G4`):**
   - FRED weekly `LNFACBW027SBOG` bank-to-NDFI loans & `%` of total US bank credit (`TOTLL`), ICE BofA EUR/US HY, BB, Single-B, and CCC OAS summary pills, and matched-frame SEC EDGAR Form `10-Q` XBRL table decomposing quarterly Gross Investment Income into **PIK Debt Interest %**, **PIK Preferred Dividend %**, and **Total Non-Cash PIK %** across 7 public BDCs.
6. **Upstream Thufir Hawat Macro-to-Credit Transmission Bridge (`thufir_bridge_html`):**
   - Explicit 4-card bridge linking Thufir's daily macro signals (FOMC rate path, AI capex vs SaaS compression, Gold/pod de-grossing, Brent crude & UK inflation) to subterranean credit channels and clickable target topic tabs (`T1`–`T6`).
7. **Decisions Requested of the CIO (`decisions` block):**
   - Exact 3 Asks (labeled `D1`, `D2`, `D3`) presented in a 3-column grid. Each card displays an ID badge, explicit Ask heading, `Why` operational rationale, and `Impact` statement.
8. **Opportunities to Anticipate vs Hard Vetoes Grid (2-Column Layout):**
   - **Opportunities (`O1`, `O2`, `O3`):** Green-accented cards (`border-left: 3px solid var(--green);`) detailing the asymmetric trade thesis, `Why now` catalyst, and `Verify` prerequisites.
   - **Hard Vetoes (`V1`, `V2`, `V3`):** Red-accented cards (`border-left: 3px solid var(--red);`) declaring mandatory dealing prohibitions (e.g. litigation-led debtor stacks, junior water WBS tranches, post-RP BB mezzanine and software-heavy BDC equity).
9. **Consolidated `alpha-g` `StructuredCreditSignalRecord` Factor Matrix (`vectors_table_html`):**
   - Full tabular readout of all emitted quantitative factor vectors (`deal_or_loan_id`, `topic`, `market_jurisdiction`, `ccc_bucket_percentage`, `junior_oc_cushion_bp`, `warf_score`, `was_spread_bp`, `lme_priming_risk_index`, `default_intensity_forecast`, `half_life_days`, `action_gate`, and sealed evidence reference).
10. **Risk Map (5x5 Heatmap) vs Transmission Map (Mermaid Flowchart):**
   - **Risk Heatmap:** 5x5 matrix mapping Probability (1 to 5) against Impact (1 to 5). Cells are shaded dynamically (`hsla(hue, 62%, 45%, 0.30)`) with interactive topic tags (`⚡ T2`, `📉 T4`).
   - **Transmission Map:** Directional Left-to-Right Mermaid flowchart (`flowchart LR`) tracing systemic transmission from tight liabilities and loan repricings down through CCC migration, OC cliff pressure, and cash diversions.
11. **Catalyst Calendar vs Evidence Integrity Bar:**
   - **Timeline (`.timeline`):** Vertical milestone tree with dates, topic IDs, event titles, and notes.
   - **Evidence Integrity Bar (`.integrity`):** Proportional stacked horizontal bar illustrating the exact composition of figures by provenance, plus open data gaps (`G1`–`G5`).

---

### 3.3 Tabs 1–6 — The Five Mandatory Sections Per Topic Tab
Each topic tab represents an exhaustive credit deep-dive adhering to the mandatory 5-section sequence:

#### Topic Header Card:
- Large Emoji square (`76px x 76px`, `font-size: 38px`, `background: var(--panel-2)`).
- Topic Code & Census (e.g. `T1 · TOPIC 1 OF 6`), H2 Title, and Executive Thesis.
- Restated Evidence Chips (`<span class="tag tag-cyan">E01</span>`).
- Right-aligned Verdict box (`.v`) and Stance badge (`.s`).
- **Freshness strip (v5, `freshness_html`):** 🆕 NEW TOPIC (catalyst date · type) or ♻️ RUNNING — NOT CLOSED (open since · latest catalyst · type), catalyst evidence chips, and for RUNNING topics a mandatory **"What is new today"** line. When a running situation has no fundamental news, the delta must say so plainly and label the move as market-only telemetry.

#### Section 1: Signal — What Moved
- Provenance class: `sourced` (enforced by the pre-publish guard).
- Documents what occurred in the physical market, rating agency print, court docket, or trustee report.
- **ABSOLUTE RULE — BARE NUMBER SCAN:** Not a single raw number, dollar/euro/pound amount, basis point, or percentage may appear as bare text. Every quantity MUST be injected via `[[Fxx]]` figure tokens.

#### Section 2: Forensic Mechanism & Mathematical Formulation
- Deconstructs legal indentures, unrestricted subsidiary designations, double-dip structures, and waterfall cash diversions.
- **LaTeX Formula Integration:** Contains an explicit mathematical formulation with MathJax typesetting (`$$...$$`), a formula status badge, and an explanatory mathematical note.
  - Formula Status Badges (`LATEX_STATUS`):
    * `identity`: *Identity — exact by construction* (Green · `derived`)
    * `standard`: *Market-standard definition, simplified* (Cyan · `derived`)
    * `approximation`: *Practitioner approximation* (Amber · `estimate`)
    * `framework`: *Stylised framework — not calibrated* (Mauve · `illustrative`)
- **Optional Capital Stack Visualizer (`show_stack`):** Visual proportional stacked bar diagram representing the tranches of a capital structure (AAA, AA, A, BBB, BB, B, Equity) with percentage allocations and color tiers.

#### Section 3: Factor Map
- Unordered list (`.factor-list`) with gold diamond bullets (`◆`) identifying the key institutional drivers, covenant loopholes, rating agency criteria, and cross-asset contagion vectors.

#### Section 4: Scenarios & Kill Switch
- 3-Scenario forward matrix rendered in a 3-column grid:
  - **Scenario A (Base Case):** Emerald/Gold styling, estimated probability, probability progress bar (`.bar`), and concise scenario trajectory.
  - **Scenario B (Alternative Case):** Amber styling, estimated probability, progress bar, and friction/reopening trajectory.
  - **Scenario C (Tail / Stress Case):** Crimson/Amber styling, estimated probability, progress bar, and downside trajectory.
  - **Probability Invariant:** $P_A + P_B + P_C = 100\%$ exactly (validated by guard).
  - **Mandatory Kill Switch:** Scenario C MUST feature an explicit, highlighted **Kill Switch** box (`.kill`) specifying the exact quantitative market level, court ruling, or rating downgrade that renders the thesis void and revokes dealing authority.

#### Section 5: Positioning & Verification
- **Posture:** Concrete trading and portfolio stance (e.g. underwriting restrictions, secondary mezzanine targets, basis hedges).
- **Verify Next:** Specific upcoming data releases, court dockets, trustee dates, or conference calls required to validate the thesis.
- **Scored Calls:** Bullet list of registered falsifiable market calls for this topic, quoting Call ID, probability $p$, conviction band, and resolution deadline.
- **Open Gaps:** Tagged list of open data gaps affecting this credit.

---

### 3.4 Tab 7 — Provenance & Call Ledger (The Sceptical Reader's Haven)
Tab 7 provides total transparency into data integrity, analyst accountability, and source attribution:
1. **Evidence Integrity & Methodology Note:** Card explaining that every figure in the dossier is a registered object with provenance, citing sealed notes or explicit rationales.
2. **Call Ledger (The OODA Reflect Loop):**
   - Active track record statistics: Total calls scored, hit rate percentage, Brier calibration score, pending calls count, and active conviction cap (`LOW`, `MEDIUM`, or `HIGH`).
   - Interactive table listing all active and historical calls with Call ID, Topic, Proposition, $p$, Band, Resolve By date, and Status.
3. **Data Gap Register:** Table listing every open residual data gap (`G1`–`G5`), what remains behind private paywalls, the analytical consequence, and the proposed procurement or `inbox/` drop-in remedy.
4. **SEC EDGAR Form `NPORT-P` Deal-Level CLO Tranche Telemetry (`clo_tranches_html` — Gap `G1` Narrowed):** Pool-level and representative/discount-tail deal-level CLO tranche table across `JAAA`, `JAA_A`, and `JBBB` (tranche counts, par, par-weighted clean mark, floating coupon, `< 99.0` tail share, top manager shelves, and direct EDGAR XML archive links).
5. **Statutory UK High Court Case Law XML & SEC EFTS Restructuring Filings (`court_dockets_html` — Gap `G2` Narrowed):** Point-in-time Chancery / Part 26A High Court judgments and SEC `8-K`/`6-K`/`NPORT-P` restructuring filings with direct statutory archive links.
6. **Figure Register:** Exhaustive tabular register of every single figure token used in the dossier (`ID`, `Figure Label`, `Formatted Value`, `Provenance Key`, `Confidence`, `As Of Date`, and `Evidence / Rationale Basis`).
7. **Sealed Evidence Capture Notes:** Tabular inventory of raw capture notes (`ID`, `Capture Title`, `Publishers`, `Captured UTC`, and truncated SHA-256 seal) with expandable `<details>` accordions showing the full raw text excerpt and query string.
8. **Bibliography (Source Registry):** Audit table linking every used source to its entry in `structured_credit_intelligence_sources.json`, displaying Tier, Name, Reliability Rating, and specific usage.
9. **Analyst Heuristics Carried Forward:** Formal inventory of Chrizza's operational rules of thumb (`H1`, `H2`...).
10. **Build Manifest:** Cryptographic table displaying the file path and SHA-256 hash of every script, sweeper, watchlist, template, schema, and payload that generated the build.

---

## 4. 🧬 Figure Registry, Provenance Keys & Tokenization Rules

### 4.1 Provenance Hierarchy
Every figure in a Chrizza dossier MUST be registered with one of four canonical provenance classes:

| Provenance Key | CSS Token | Front-Page Underline | Definition & Evidentiary Standard |
|---|---|---|---|
| **`sourced`** | `.fig-sourced` | Green Dotted | Restated directly from a sealed capture note (`E01`–`Exx`). Must cite a valid `evidence` ID and have an `as_of` date within the last 60 days. |
| **`derived`** | `.fig-derived` | Cyan Dotted | Computed mathematically from sourced figures, or exact by construction (e.g. spread differentials, ratios). Must list input figures in `inputs`. |
| **`estimate`** | `.fig-estimate` | Amber Dotted | Chrizza's quantitative judgement or heuristic assessment. Must declare an explicit `rationale`. Falsifiable estimates must register in the call ledger. |
| **`illustrative`** | `.fig-illustrative` | Mauve Dotted | Stylized teaching example, standard capital stack share, or theoretical model. Not live market data. |
| **`gap`** | `.prov-gap` | Red Marker | Data missing. Explicit marker that no claim is made. |

### 4.2 Strict Bare-Number Prohibition in Prose
The pre-publish guard scans all prose strings across the content payload. Any bare number, currency amount (`€`, `$`, `£`), basis point (`bp`, `bps`), percentage (`%`), or magnitude (`bn`, `million`, `x`) that is not wrapped inside a figure token `[[Fxx]]` will **immediately fail the build**:
- ❌ **Forbidden:** `"AAA new issue cleared at 124 bps in September."`
- ✅ **Mandatory:** `"AAA new issue cleared at [[F01]] in September."`

Where `F01` is formally declared in `content["figures"]`:
```json
"F01": {
  "label": "EUR CLO AAA new-issue average spread, Sep 2026",
  "display": "124 bps",
  "value": 124.0,
  "unit": "bps",
  "provenance": "sourced",
  "evidence": "E01",
  "confidence": "medium",
  "as_of": "2026-09-30"
}
```

---

### 4.3 Topic Freshness Contract (v5)
| Status | Catalyst | Max age (business days after catalyst) | Extra requirement |
|---|---|---|---|
| **🆕 NEW** | `news` — at least one `search_web` capture in `catalyst_evidence` | ≤ 5 (one trading week) | Title and `thread` must not appear in the prior edition |
| **♻️ RUNNING — NOT CLOSED** | `news` or `telemetry` | ≤ 10 | `delta` ("what is new today") required and must not repeat the prior edition verbatim |

Every edition needs at least one NEW topic. Open situations may keep running for as long as something genuinely moves; when nothing moves they are retired from the tabs and listed on the Tab 0 freshness board, never re-published unchanged. Windows count Mon–Fri only (`business_days_between`), calibrated on 2026-11-07 for a niche, weekly-cadence market and **ratified by the Agent Manager** the same day.

### 4.4 Independence Protocol (v5)
Every evidence item declares an `origin`:
| Origin | Meaning | Tag |
|---|---|---|
| `chrizza_native` | Found by Chrizza's own open domain search, run **before** reading Thufir's dossier, with no Thufir-sourced names in the query | 🦅 Chrizza-native |
| `thufir_seeded` | Lead taken from Thufir's dossier (or a search whose query names his stories) | 🔭 Thufir-seeded |
| `telemetry` | Chrizza's deterministic sweepers (FMP, FRED, EDGAR, ISINs, dockets) | 📡 Telemetry |

The guard fails the build if any item lacks a valid origin or if **no NEW topic cites a `chrizza_native` catalyst**. Origins render in the Tab 7 evidence table and the Tab 0 freshness board, with an "Evidence independence" census. Thufir's bridge cards remain as context; his stories become topics only with credit-specific verification.

---

## 5. 🎯 The Call Ledger & Brier Score Conviction Governance

Chrizza does not issue un-calibrated opinions. Analyst conviction is governed by an automated, self-limiting feedback loop:

### 5.1 Conviction Bands
A forecast probability $p \in [0.0, 1.0]$ is categorized by its absolute distance from an uninformative coin flip ($|p - 0.5|$):
- **`low`:** $|p - 0.5| < 0.15$ ($0.35 < p < 0.65$)
- **`medium`:** $0.15 \le |p - 0.5| < 0.30$ ($0.20 \le p \le 0.35$ or $0.65 \le p \le 0.80$)
- **`high`:** $|p - 0.5| \ge 0.30$ ($p \le 0.20$ or $p \ge 0.80$)

### 5.2 Dynamic Conviction Cap Rule
The highest conviction band permitted in any dossier is capped by the analyst's historical track record in `chrizza_call_ledger.json`:
1. **Cold Start Rule:** Until at least **10 calls** have been formally scored against verified real-world outcomes, the conviction cap is locked at **`MEDIUM`**. No `high` conviction call ($p \ge 0.80$ or $p \le 0.20$) may be registered.
2. **Promotion to High:** Requires $\ge 10$ scored calls, a **hit rate $\ge 70\%$**, and a **Brier score $\le 0.18$**.
3. **Demotion to Low:** If the hit rate falls below $50\%$ or Brier score exceeds $0.25$ over $\ge 10$ calls, the cap drops to **`LOW`**.
4. **Enforcement:** If a content JSON contains a call whose band exceeds the ledger's active cap, `ops_chrizza_pre_publish_guard.py` **aborts the render with exit code 1**.

---

## 6. 🚀 Step-by-Step Start of Day (SOD) Execution Pipeline

The daily intelligence cycle executes across six disciplined stages:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 0: PRE-FLIGHT INVARIANT & TEMPLATE SYNC                               │
│  - Verify canonical template and sync runtime mirror                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ STAGE 1: OBSERVE — UNIFIED TELEMETRY SWEEP & EVIDENCE CAPTURE               │
│  - Sweep FMP proxies + all 4 Data-Gap feeds: `sweep-all --date <YYYYMMDD>`  │
│  - Execute targeted searches across Tier 1–4 credit endpoints               │
│  - Capture raw excerpts, URLs, and publisher metadata                        │
│  - Populate `credit_evidence_<date>.json`                                   │
│  - Seal evidence: `ops_chrizza_generate_credit_dossier.py seal`             │
├─────────────────────────────────────────────────────────────────────────────┤
│ STAGE 2: ORIENT & DECIDE — CONTENT AUTHORING & FIGURE TOKENIZATION          │
│  - Author `credit_content_<date>.json` conforming to canonical schema       │
│  - Register all metrics into `figures` dictionary (`[[F01]]`–`[[Fxx]]`)     │
│  - Compose 5 mandatory sections per topic tab                               │
│  - Verify scenario probabilities sum to 100%                                │
│  - Register falsifiable calls within the active conviction cap              │
├─────────────────────────────────────────────────────────────────────────────┤
│ STAGE 3: FAIL-CLOSED GUARD PRE-FLIGHT                                       │
│  - Execute `ops_chrizza_pre_publish_guard.py`                               │
│  - Verify zero bare numbers, valid LaTeX, fresh data, and template sync     │
├─────────────────────────────────────────────────────────────────────────────┤
│ STAGE 4: ACT — DETERMINISTIC COMPILATION & DOSSIER EMISSION                 │
│  - Render HTML: `ops_chrizza_generate_credit_dossier.py render`             │
│  - Verify build manifest SHA-256 hashes                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ STAGE 5: REFLECT — CALL LEDGER SYNC & MEM-JOG AUDIT                         │
│  - Register new calls into `chrizza_call_ledger.json`                       │
│  - Score any matured calls past `resolve_by` with cryptographic evidence    │
│  - Log hits, misses, and covenant traps in `MEM-JOG`                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Step 0: Pre-Flight Invariant & Template Sync
Ensure the canonical template in `DOCS/4_operate/templates/` is mirrored byte-identically into `roc/scripts/ops_chrizza/templates/`:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py sync-template
```

---

### Step 1: Observe — Unified Market, Statutory & Exchange Sweep + Evidence Capture
1. Execute the unified v4 telemetry sweep (`sweep-all`), which runs `sweep-quotes` (`credit_quotes_<YYYYMMDD>.json`) plus all four deterministic Data-Gap sweepers (`ops_chrizza_sweep_bond_isins.py`, `ops_chrizza_sweep_nbfi_and_bdc.py`, `ops_chrizza_sweep_clo_nport.py`, and `ops_chrizza_sweep_court_dockets.py`) driven by `roc/config/structured_credit_isin_watchlist.json` (and normalizes any operator drops in `roc/scripts/ops_chrizza/inbox/trustee/` or `inbox/dockets/`):
```bash
python roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py sweep-all --date <YYYYMMDD>
```
   *(Individual sub-sweeps remain callable via `sweep-quotes --date <YYYYMMDD>` and `sweep-gaps --date <YYYYMMDD>`.)*
2. Ingest the curated source endpoints from `roc/config/structured_credit_intelligence_sources.json`.
3. Prioritize high-utility Tier 1 credit desks (Creditflux, 9fin, PitchBook LCD, Trepp, Octus) and Tier 2 rating agency research (Fitch, Moody's, S&P).
4. Search and extract raw credit notices, trustee monthly distribution summaries, court filings, and restructuring plans.
   - **News-first discovery (v5):** run *open* searches for the last trading week of structured credit, leveraged loan, private credit, CLO and restructuring news **before** looking at the watch-list, yesterday's dossier **or Thufir's dossier**. Queries must not contain names taken from Thufir. Capture every material story as a `search_web` evidence item with `origin: "chrizza_native"` and its event date in the excerpt.
   - Only after the native sweep, read Thufir's dossier for the bridge; any story taken from it is captured with `origin: "thufir_seeded"` and must be verified for credit relevance (and reconciled where figures disagree) before it can become a topic.
   - Only then sweep the open threads from the previous edition (`prior_content`) for genuine developments. A thread with no development is either dropped (it will appear as `retired` on the freshness board) or carried as RUNNING with an honest market-only delta.
   - Sweeper telemetry (`capture_method` = a sweeper script) can justify a RUNNING delta but **never a NEW topic**.
5. Construct `roc/scripts/ops_chrizza/evidence/credit_evidence_<YYYYMMDD>.json`:
```json
{
  "schema": "chrizza.evidence.v1",
  "dossier_id": "CHZ-CREDIT-YYYYMMDD",
  "observed_at_utc": "YYYY-MM-DDT07:00:00Z",
  "items": [
    {
      "id": "E01",
      "title": "September 2026 European CLO Monthly Activity Report",
      "publisher_domains": ["creditflux.com", "trepp.com"],
      "query": "european clo monthly report september 2026 issuance refi reset aaa spreads",
      "captured_at_utc": "YYYY-MM-DDT06:30:00Z",
      "excerpt": "September European CLO new issue reached €7.6bn across 17 deals, while refi and reset activity printed €3.1bn. AAA spreads cleared at an average of 124 bps for new issue and 120 bps for resets...",
      "sha256": ""
    }
  ],
  "method_note": "Intelligence harvested across Tier 1–4 credit endpoints with point-in-time cryptographic seals."
}
```
5. Seal the evidence file (computes immutable SHA-256 hashes over raw excerpts):
```bash
python roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py seal --date <YYYYMMDD>
```

---

### Step 2: Orient & Decide — Content Authoring & Figure Registration
Construct `roc/scripts/ops_chrizza/content/credit_content_<YYYYMMDD>.json`:
1. **Declare Metadata:** `dossier_id`, `title`, `observed_at_utc`, `session_for`, `author`, `audience`.
2. **Build Figures Register (`figures`):**
   - Assign every number a unique token (`F01`, `F02`...).
   - Specify label, display string ($\le 34$ chars; $\le 16$ chars with zero parentheses/semicolons for any figure used in `brief.pulse`), numerical value, unit, provenance class (`sourced`, `derived`, `estimate`, `illustrative`), confidence (`high`, `medium`, `low`), and evidence reference or rationale.
3. **Declare Open Gaps (`gaps`):** Record missing data points (`G1`–`G5`), analytical impact, and remedy.
4. **Draft Tab 0 Command Brief (`brief`):**
   - Regime label, headline, BLUF summary, credit regime score figure ID.
   - KPI pulse list (4 entries referencing figure IDs; each `label` $\le 28$ chars and each referenced figure `display` $\le 16$ chars with no parenthetical/semicolon subtext).
   - 3 Decisions requested of the CIO (`D1`, `D2`, `D3`).
   - 3 Opportunities (`O1`, `O2`, `O3`) and 3 Hard Vetoes (`V1`, `V2`, `V3`).
   - Mermaid transmission flowchart string.
   - Catalyst calendar items.
5. **Select today's six topics (v5 freshness contract) before writing any prose:**
   - Rank the day's news captures by credit materiality; take NEW topics from the top of that list (**at least one NEW topic per edition, and at least one of those Chrizza-native**).
   - Fill remaining tabs with RUNNING threads from the previous edition only where there is a dated development (≤ 7 days) or an honest market-only delta.
   - Retire threads that have neither; do not keep a story because it is on the watch-list or was on yesterday's page.
   - Recommended build: author in guarded chunks (figures → brief → NEW topics → RUNNING topics + calls/vectors/gaps), running the guard checks after each chunk; prefer a lean register (~70–100 figures) over volume.
6. **Draft Tabs 1–6 Topics (`topics`):**
   - For each topic: `id`, `emoji`, `short_title` (mandatory concise whole-word tab title $\le 28$ chars so top navigation tab pills never truncate mid-word), `title`, `thesis`, `verdict`, `stance`, `risk` (probability & impact 1–5), `evidence` citations, `verify` notes.
   - **`freshness` block (mandatory, v5):**
     ```json
     "freshness": {
       "thread": "stable_snake_case_story_key",
       "status": "new | running",
       "catalyst_type": "news | telemetry",
       "first_reported": "YYYY-MM-DD",
       "latest_catalyst": "YYYY-MM-DD",
       "catalyst_evidence": ["E0x"],
       "delta": "RUNNING only — what is new today, with [[Fxx]] tokens"
     }
     ```
   - **`watch_themes` (optional):** list of watch-list themes this topic claims (e.g. `["thames_water_wbs"]`), which links those ISINs on the bond tape to this tab.
   - **Legacy calls:** re-map pending ledger calls to the topic that covers them *today* (the ledger keeps its original topic); never let an old topic ID point at a different story.
   - **Section 1 (`signal`):** Prose utilizing `[[Fxx]]` tokens.
   - **Section 2 (`mechanism`):** Indenture analysis + LaTeX formula + formula status badge + optional capital stack.
   - **Section 3 (`factors`):** List of driving structural factors.
   - **Section 4 (`scenarios`):** Scenarios A, B, C with probabilities summing to 100% and Scenario C kill switch.
   - **Section 5 (`posture`):** Portfolio positioning stance and verify next.
7. **Formulate Scored Calls (`calls`):**
   - Minimum 1 scorable proposition per major topic.
   - Verify probability $p$ does NOT breach the active conviction cap.
8. **Incremental Chunk Validation & Assembly (`ops_chrizza_content_builder.py`):**
   - Author fragments under `roc/scripts/ops_chrizza/content/fragments/<YYYYMMDD>/` (`figures.json`, `brief.json`, `topics.json`, `tail.json`), validate each chunk immediately, and assemble:
   ```bash
   python roc/scripts/ops_chrizza/ops_chrizza_content_builder.py check-chunk --date <YYYYMMDD> --chunk all
   python roc/scripts/ops_chrizza/ops_chrizza_content_builder.py assemble --date <YYYYMMDD>
   ```

---

### Step 3: Fail-Closed Guard Pre-Flight
Run the comprehensive pre-publish validation suite:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_pre_publish_guard.py --date <YYYYMMDD>
```
If any defect is reported (bare number detected, stale sourced figure, mismatched evidence hash, invalid LaTeX syntax, unclosed braces, or scenario probability sum $\ne 100$), **halt and fix the content JSON**. Never bypass or weaken the guard.

---

### Step 4: Act — Deterministic Compilation & Dossier Rendering
Render the production HTML artifact into `DOCS/4_operate/`:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py render --date <YYYYMMDD>
```
Verify the output exists:
`DOCS/4_operate/Ops_Structured_Credit_CLO_Horizon_Dossier_<YYYYMMDD>.html`

---

### Step 5: Reflect — Call Ledger Sync & Track Record Scoring
1. Register new probabilistic calls into `chrizza_call_ledger.json`:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_learning_ledger.py register --date <YYYYMMDD>
```
2. Check for any pending calls that have reached their resolution date:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_learning_ledger.py due --as-of <YYYY-MM-DD>
```
3. Score any matured calls against primary source documentation:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_learning_ledger.py score --id <CALL_ID> --outcome <yes|no> --evidence "<Primary Source Docket / Trustee Report Link>"
```
4. View updated Brier calibration stats:
```bash
python roc/scripts/ops_chrizza/ops_chrizza_learning_ledger.py stats
```
5. Update [`.agent/skills/structured-credit-agent/MEM-JOG-Chrizza-Structured-Credit-And-CLO-Forensics-Bible.md`](.agent/skills/structured-credit-agent/MEM-JOG-Chrizza-Structured-Credit-And-CLO-Forensics-Bible.md) with newly acquired heuristics, misses, and lessons learned.

---

## 7. 🛡️ Fail-Closed Guard Verification Checklist (Pre-Publish Rules)

The guard (`ops_chrizza_pre_publish_guard.py`) enforces the following non-negotiable checks:

| Domain | Invariant Rule | Failure Consequence |
|---|---|---|
| **Template Sync** | `CANONICAL_TEMPLATE` and `MIRROR_TEMPLATE` must be byte-identical. | `Mirror drift detected` ➔ Run `sync-template` |
| **Evidence Seals** | `sha256(item["excerpt"])` must match `item["sha256"]`. | `Compromised evidence seal` ➔ Run `seal` |
| **Telemetry & Gap Seals** | `credit_quotes_<date>.json` and all 4 v4 Data-Gap JSONs (`bond_isins`, `nbfi_bdc`, `clo_tranches`, `court_dockets`) must match `seal_payload(doc)` and domain bounds (`check_gap_feeds`). | `Payload sha256 seal / domain mismatch` ➔ Run `sweep-all` |
| **Data Freshness & Derived Math** | Sourced figures (`as_of`) must be $\le 60$ days old unless stamped `historical: true`; derived figures must declare `op` $\in$ `("diff", "diff_bp", "sum", "ratio_pct")` and pass exact arithmetic check against `inputs`. | `Stale sourced figure (>60 days)` / `derived figure op / value mismatch` |
| **Bare Number Scan** | Zero raw numbers, currency, bps, or % in prose strings (`PROSE_KEYS`). | `Bare quantity in prose` ➔ Wrap into `[[Fxx]]` |
| **Token Validity & Display Length** | Every `[[Fxx]]` token in prose must exist in `content["figures"]`, and every figure `display` must be $\le 34$ chars (`FIGURE_DISPLAY_MAX_CHARS`). | `Dangling figure token` / `exceeds 34-char inline figure token limit` |
| **KPI Pulse Card Anti-Overspill** | Every `brief.pulse` card `label` must be $\le 28$ chars (`PULSE_LABEL_MAX_CHARS`), and its figure `display` must be $\le 16$ chars (`PULSE_VALUE_MAX_CHARS`) with no `(` or `;`. | `causes KPI card value/title overspill` ➔ Move detail to `pulse.sub` |
| **Topic Tab `short_title` Guard** | Every topic with `len(title) > 28` must define an explicit whole-word `short_title` $\le 28$ chars (`SHORT_TITLE_MAX_CHARS`). | `causing tab button truncation` ➔ Add `short_title` ($\le 28$ chars) |
| **HTML Card Anti-Overspill CSS** | Rendered HTML must include `.kpi .kpi-value .fig` and `overflow-wrap: break-word` rules. | `missing KPI card anti-overspill CSS` ➔ Run `sync-template` & `render` |
| **LaTeX Sanity** | Balanced curly braces, allowlisted TeX macros, zero control characters/tabs. | `TeX macro / syntax error` |
| **Scenario Sum** | $P_A + P_B + P_C = 100\%$ for every topic. | `Scenario probabilities do not sum to 100` |
| **Kill Switch** | Scenario C must define a concrete `kill_switch` string. | `Missing Scenario C kill switch` |
| **Conviction Cap** | No call may have a conviction band higher than `stats(ledger)["cap"]`. | `Call breaches active conviction cap` |
| **Slots & Leaks** | Rendered HTML must have zero unfilled `{{SLOT}}` tags and no leaked `null`/`NaN`. | `Unfilled slot / None leak in HTML` |
| **Lock Prohibition** | Agent must not stamp template or dossier with self-applied 💎 locks. | `Self-applied lock detected` |
| **Topic Freshness (v5)** | Every topic declares `freshness`; NEW = `news` catalyst ≤ 5 business days with a `search_web` capture; RUNNING = catalyst ≤ 10 business days plus a non-empty `delta` that does not repeat the prior edition; ≥ 1 NEW topic per edition. Editions observed before 2026-11-07 are grandfathered. | `latest catalyst is N business days old` / `NEW topic must be driven by a news catalyst` / `delta repeats the prior dossier verbatim` |
| **Independence (v5)** | Every evidence item has `origin` ∈ {`chrizza_native`, `thufir_seeded`, `telemetry`}; ≥ 1 NEW topic cites a `chrizza_native` catalyst; `check_independence` verifies `chrizza_native` queries contain no Thufir-seeded lead tokens/tickers and checks capture timestamps against upstream Thufir exposure (requiring `native_after_exposure: true` and UI disclosure when captured post-exposure). | `must declare origin` / `query contains Thufir-seeded lead token(s)` / `captured after upstream Thufir exposure without 'native_after_exposure': true` |
| **Story Threads (v5)** | `thread` is a unique snake_case key per topic; a NEW topic may not reuse a prior-edition thread or title. | `thread must be a stable snake_case story key` / `continues a prior-edition story — mark it 'running'` |
| **No Hardcoded Topics (v5)** | Watch-list carries `theme` only; sweepers/renderer use no issuer or topic literals; bond tape links only themes claimed by today's `watch_themes`. | Covered by tests `test_bond_tape_links_only_themes_claimed_by_current_topics` |

---

## 8. 📡 Downstream Handoff to Alpha-G & Upstream Ingress from Thufir

```
         ┌────────────────────────────────────────────────────────┐
         │                      THUFIR HAWAT                      │
         │          Macro Headlines & Geopolitical Sentiment      │
         └───────────────────────────┬────────────────────────────┘
                                     │ (1) Inbound Credit Anomaly Flags
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │                        CHRIZZA                         │
         │     Subterranean Debt Plumbing & CLO Forensics         │
         └───────────────────────────┬────────────────────────────┘
                                     │ (2) Structured Credit Vectors & Priming VETOs
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │                        ALPHA-G                         │
         │         Alpha Designer & Multi-Asset Execution         │
         └────────────────────────────────────────────────────────┘
```

1. **Upstream Inbound from Thufir:** Chrizza monitors inbox for macro credit alerts (e.g. US HY OAS spread widening, cross-border banking strains).
2. **Downstream Outbound to Alpha-G:**
   - **Hard Dealing Vetoes:** whatever vetoes the current edition publishes (`brief.vetoes`) — re-justified each day from current evidence, never carried by default.
   - **Vector Emission:** Structured credit vectors conforming to `StructuredCreditSignalRecord`:
     * `junior_oc_cushion_bp`
     * `ccc_bucket_percentage`
     * `lme_priming_risk_index` $[0.0, 1.0]$
     * `half_life_days` ($\tau$ structural decay)
     * `default_intensity_forecast`

---

## 9. 🏁 Definition of Done (DoD)

A Chrizza Start of Day cycle is formally complete when and only when:
1. `sweep-all --date <date>` has swept and SHA-256-sealed `credit_quotes_<date>.json`, `credit_bond_isins_<date>.json`, `credit_nbfi_bdc_<date>.json`, `credit_clo_tranches_<date>.json`, and `credit_court_dockets_<date>.json`.
2. `credit_evidence_<date>.json` is populated and sealed with valid SHA-256 hashes.
3. `credit_content_<date>.json` is fully authored with all figures tokenized into `figures` dictionary.
4. `ops_chrizza_pre_publish_guard.py` passes with **0 defects** (including `check_gap_feeds`).
5. `Ops_Structured_Credit_CLO_Horizon_Dossier_<date>.html` is compiled into `DOCS/4_operate/` with valid MathJax rendering, responsive SVG brand marks, live statutory/exchange telemetry cards, and interactive tabs.
6. All new calls are registered in `chrizza_call_ledger.json`.
7. Retrospective observations and new heuristics are committed to `MEM-JOG-Chrizza-Structured-Credit-And-CLO-Forensics-Bible.md`.
8. **Freshness & independence (v5):** every topic is badged NEW or RUNNING with a dated catalyst, the Tab 0 freshness board lists today's threads, their origin and the prior edition's retired stories, every evidence item carries an origin, at least one NEW topic is Chrizza-native, and no topic was selected because of the watch-list, yesterday's line-up or Thufir alone.

*— Ratified by Princess Irulan, Lead Evolutionary Architect 🏛️💎*
