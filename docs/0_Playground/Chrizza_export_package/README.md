# Chrizza (`structured-credit-agent`) — Portable Export Package

> **Agent:** Chrizza — Lead Structured Credit, CLO & Leveraged Debt Intelligence Specialist (`structured-credit-agent`)  
> **Creed:** *"O paliós eínai alliós, allá o néos eínai oraíos."*  
> **Portability Contract:** 100% workspace-relative (`ROOT = Path(__file__).resolve().parent.parents[2]`). Zero dependency on the parent workspace being named `SGIP_Investing`.

---

## 1. Quick Start on the Target Machine

Copy this entire `Chrizza_export_package/` folder to the target machine, then run:

```bash
# Step 1: Verify cryptographic SHA-256 integrity of all packaged artefacts
python init_chrizza_workspace.py verify-package

# Step 2: Install into your new workspace root (can have ANY directory name) and run full verification
python init_chrizza_workspace.py install --target /path/to/your_new_workspace --verify
```

The `--verify` flag automatically runs inside `/path/to/your_new_workspace`:
1. `python roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py sync-template`
2. `python roc/scripts/ops_chrizza/ops_chrizza_pre_publish_guard.py --date 20261107 --html DOCS/4_operate/Ops_Structured_Credit_CLO_Horizon_Dossier_20261107.html`
3. `python -m pytest roc/scripts/ops_chrizza/test_ops_chrizza_dossier.py -q` (`65 passed`)

---

## 2. Relative Workspace Layout Installed by `init_chrizza_workspace.py`

All paths inside `payload/` are relative to `<TARGET_WORKSPACE_ROOT>`:

```text
<TARGET_WORKSPACE_ROOT>/
├── .agent/
│   ├── skills/
│   │   ├── character-substrate/
│   │   │   └── SKILL.md                                                 # R58 Universal character judgement layer
│   │   └── structured-credit-agent/
│   │       ├── SKILL.md                                                 # Chrizza genome & factor taxonomy
│   │       └── MEM-JOG-Chrizza-Structured-Credit-And-CLO-Forensics-Bible.md
│   └── workflows/
│       ├── operate-chrizza-structured-credit-dossier-report.md          # /operate-chrizza-structured-credit-dossier-report
│       └── create-mem-jog.md
├── DOCS/
│   └── 4_operate/
│       ├── templates/
│       │   └── Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html  # Canonical master HTML template (🦅💎)
│       └── Ops_Structured_Credit_CLO_Horizon_Dossier_20261026..20261107.html  # 6 reference HTML dossiers
├── roc/
│   ├── config/
│   │   ├── structured_credit_intelligence_sources.json                  # Tier 1–4 source registry
│   │   └── structured_credit_isin_watchlist.json                        # De-hardcoded theme watchlist (v5)
│   ├── DOCS/
│   │   ├── assets/images/chrizza_v1.png, chrizza_motif_v1.png
│   │   ├── comms/chrizza/{1_inbox,2_in-progress,3_archive}/
│   │   └── reports/Job_and_Persona_Spec_Chrizza_Structured_Credit_CLO_Specialist.md
│   └── scripts/
│       └── ops_chrizza/
│           ├── ops_chrizza_dossier_common.py                            # Shared paths, schemas & SHA-256 primitives
│           ├── ops_chrizza_generate_credit_dossier.py                   # Core dossier compiler & telemetry orchestrator
│           ├── ops_chrizza_pre_publish_guard.py                         # Fail-closed guard (v5 freshness + independence)
│           ├── ops_chrizza_content_builder.py                           # Incremental chunk validator & assembler (v5)
│           ├── ops_chrizza_learning_ledger.py                           # Brier score & conviction cap calibration
│           ├── ops_chrizza_sweep_bond_isins.py                          # Gap G5 Eurobond/WBS ISIN order-book sweeper
│           ├── ops_chrizza_sweep_nbfi_and_bdc.py                        # Gaps G3/G4 FRED H.8, OAS & EDGAR BDC 10-Q XBRL
│           ├── ops_chrizza_sweep_clo_nport.py                           # Gap G1 SEC EDGAR Form NPORT-P CLO tranches
│           ├── ops_chrizza_sweep_court_dockets.py                       # Gap G2 UK High Court XML & SEC EFTS filings
│           ├── test_ops_chrizza_dossier.py                              # 65 unit & integration tests
│           ├── chrizza_call_ledger.json                                 # Active probabilistic call ledger
│           ├── templates/Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html
│           ├── content/
│           │   ├── credit_content_20261026..20261107.json               # 6 historical & current content editions
│           │   └── fragments/20261107/{figures,brief,topics,tail}.json  # v5 incremental content fragments
│           ├── evidence/
│           │   └── credit_{evidence,quotes,bond_isins,clo_tranches,court_dockets,nbfi_bdc}_*.json
│           ├── vectors/
│           │   └── credit_vectors_20261028..20261107.json               # Emitted StructuredCreditSignalRecord JSONs
│           └── inbox/{trustee,dockets}/                                 # Drop-in folders for private reports/PDFs
└── sgc/
    ├── config/
    │   ├── credentials.toml.example                                     # Sanitized template for FMP & FRED API keys
    │   └── credentials.toml                                             # Auto-scaffolded on install if missing
    └── crates/sgc-app/ui/src/
        ├── assets/infinix-brand-logo.svg                                # Masthead left brand mark
        └── app/sgc-top-status-bar.ts                                    # Masthead right SGC brand mark source
```

---

## 3. Configuring Live API Keys on the Target Machine

1. Edit `<TARGET_WORKSPACE_ROOT>/sgc/config/credentials.toml` (auto-scaffolded from `credentials.toml.example` during `install`):
   - Set `[providers.fmp].api_key` (used by `sweep-quotes`).
   - Set `[providers.fred].api_key` (used by `ops_chrizza_sweep_nbfi_and_bdc.py` for FRED H.8 and ICE BofA OAS series).
2. All other statutory and exchange sweepers (`SEC EDGAR 10-Q XBRL`, `Form NPORT-P`, `SEC EFTS`, `UK High Court Case Law XML`, and `Frankfurt/Stuttgart Eurobond ISIN order books`) require **no API key**.
3. Note on Upstream Thufir Independence:
   - On a machine without Thufir (`roc/scripts/ops_thufir/`), Chrizza operates **100% sovereignly**: `check_independence()` automatically detects the absence of `dossier_content_<YYYYMMDD>.json` and validates all `chrizza_native` and `telemetry` captures independently.

