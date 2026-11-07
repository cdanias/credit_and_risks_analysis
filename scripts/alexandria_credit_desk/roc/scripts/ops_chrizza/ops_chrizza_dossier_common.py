"""Shared paths, loaders and primitives for Chrizza's credit dossier pipeline (v3).

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (operator intelligence publishing)
    Classifier    : CC-Bear · RC-Butterfly with roc/scripts/ops_thufir
    Lock status   : UNLOCKED — awaiting Agent Manager ratification

Engine, guard, ledger and tests all import from here, so each path and schema
name is defined only once.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

TEMPLATE_NAME = "Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html"
CANONICAL_TEMPLATE = ROOT / "DOCS" / "4_operate" / "templates" / TEMPLATE_NAME
MIRROR_TEMPLATE = HERE / "templates" / TEMPLATE_NAME
CONTENT_DIR = HERE / "content"
FRAGMENTS_DIR = CONTENT_DIR / "fragments"
EVIDENCE_DIR = HERE / "evidence"
VECTORS_DIR = HERE / "vectors"
INBOX_DIR = HERE / "inbox"
INBOX_TRUSTEE_DIR = INBOX_DIR / "trustee"
INBOX_DOCKETS_DIR = INBOX_DIR / "dockets"
LEDGER_PATH = HERE / "chrizza_call_ledger.json"
REGISTRY_PATH = ROOT / "roc" / "config" / "structured_credit_intelligence_sources.json"
WATCHLIST_PATH = ROOT / "roc" / "config" / "structured_credit_isin_watchlist.json"
CREDENTIALS_PATH = ROOT / "sgc" / "config" / "credentials.toml"
OUTPUT_DIR = ROOT / "DOCS" / "4_operate"
THUFIR_CONTENT_DIR = ROOT / "roc" / "scripts" / "ops_thufir" / "content"

SEC_USER_AGENT = "SGC-Infinix-StructuredCredit-Research/1.0 (compliance@sgc-infinix.org)"
WEB_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 SGC-Infinix/1.0"

INFINIX_SVG_PATH = ROOT / "sgc" / "crates" / "sgc-app" / "ui" / "src" / "assets" / "infinix-brand-logo.svg"
SGC_LOGO_SOURCE = ROOT / "sgc" / "crates" / "sgc-app" / "ui" / "src" / "app" / "sgc-top-status-bar.ts"

SCHEMA_CONTENT = "chrizza.credit_dossier.v1"
SCHEMA_EVIDENCE = "chrizza.evidence.v1"
SCHEMA_LEDGER = "chrizza.call_ledger.v1"
SCHEMA_QUOTES = "chrizza.credit_quotes.v1"
SCHEMA_VECTORS = "chrizza.credit_vectors.v1"
SCHEMA_NBFI_BDC = "chrizza.nbfi_bdc_macro.v1"
SCHEMA_CLO_TRANCHES = "chrizza.clo_tranches.v1"
SCHEMA_COURT_DOCKETS = "chrizza.court_dockets.v1"
SCHEMA_BOND_ISINS = "chrizza.bond_isins.v1"

PROVENANCE = ("sourced", "derived", "estimate", "illustrative")
DERIVED_OPS = ("diff", "diff_bp", "sum", "ratio_pct")
CONFIDENCE = ("high", "medium", "low")
JURISDICTIONS = ("EUR_BSL", "US_BSL", "UK_WBS", "US_MM_PRIVATE")
ACTION_GATES = ("ALLOW", "WATCH", "HARD_VETO")

# Liquid exchange-traded structured credit, senior loan, bond and BDC proxies swept via FMP.
CREDIT_PROXY_META: tuple[tuple[str, str, str], ...] = (
    ("JAAA", "AAA CLO ETF", "US AAA Senior"),
    ("JBBB", "B–BBB CLO ETF", "US Mezzanine CLO"),
    ("CLOI", "IG CLO ETF", "IG Active CLO"),
    ("BKLN", "Senior Loan ETF", "US BSL Index"),
    ("SRLN", "Active Senior Loan", "Active BSL"),
    ("HYG", "USD High Yield Bond", "Cash HY Benchmark"),
    ("LQD", "USD Investment Grade", "Cash IG Benchmark"),
    ("ARCC", "Ares Capital BDC", "Tier-1 Direct Lending"),
    ("OBDC", "Blue Owl Capital BDC", "Software-Heavy BDC"),
    ("BXSL", "Blackstone Senior BDC", "First-Lien BDC"),
)
CREDIT_PROXY_SYMBOLS: tuple[str, ...] = tuple(sym for sym, _, _ in CREDIT_PROXY_META)

# What a formula honestly is: (badge text, badge colour, provenance class in the front-page key).
LATEX_STATUS = {
    "identity": ("Identity — exact by construction", "green", "derived"),
    "standard": ("Market-standard definition, simplified", "cyan", "derived"),
    "approximation": ("Practitioner approximation", "amber", "estimate"),
    "framework": ("Stylised framework — not calibrated", "mauve", "illustrative"),
}
# Provenance class of every rendered block type. Each block shows its key badge.
# "sourced" blocks may embed only sourced or derived figures (enforced by the guard).
BLOCK_PROVENANCE = {
    "signal": "sourced",
    "mechanism": "estimate", "factors": "estimate", "scenarios": "estimate", "posture": "estimate",
    "thesis": "estimate", "summary": "estimate", "regime": "estimate", "decisions": "estimate",
    "opportunities": "estimate", "vetoes": "estimate", "heatmap": "estimate", "transmission": "estimate",
    "calls": "estimate", "heuristics": "estimate", "calendar": "estimate",
    "vectors": "estimate", "thufir_bridge": "estimate",
    "integrity": "derived", "ledger_stats": "derived", "manifest": "derived",
    "evidence_notes": "sourced", "bibliography": "sourced", "proxy_tape": "sourced",
    "bond_isins": "sourced", "nbfi_bdc": "sourced", "clo_tranches": "sourced", "court_dockets": "sourced",
    "stack": "illustrative", "stress_sim": "illustrative",
}
# Non-claim marker: an open data gap — no claim is made.
NON_CLAIM_KEYS = ("gap",)
# TeX commands a dossier formula may use (all available in MathJax 3 tex-chtml).
ALLOWED_TEX = {
    "text", "frac", "sum", "prod", "approx", "le", "ge", "left", "right", "max", "min", "mathbb",
    "ell", "qquad", "quad", "times", "cdot", "mathcal", "Delta", "tau",
}

# Figure tokens used inside prose, e.g. "[[F01]]".
TOKEN_RE = re.compile(r"\[\[(F\d{2,3})\]\]")

# Evidence origin (v5 independence protocol): who found the story first.
ORIGINS = {
    "chrizza_native": ("🦅 Chrizza-native", "green"),   # found by Chrizza's own domain search, before reading Thufir
    "thufir_seeded": ("🔭 Thufir-seeded", "amber"),     # lead taken from Thufir's dossier, then searched / verified
    "telemetry": ("📡 Telemetry", "cyan"),              # Chrizza's deterministic sweepers (quotes, FRED, EDGAR, ISINs, dockets)
}


def content_path(stamp: str) -> Path:
    """Return the content JSON path for a session stamp (YYYYMMDD)."""
    return CONTENT_DIR / f"credit_content_{stamp}.json"


def fragments_dir(stamp: str) -> Path:
    """Return the content fragments directory for a session stamp (YYYYMMDD)."""
    return FRAGMENTS_DIR / stamp


def thufir_content_path(stamp: str) -> Path:
    """Return the upstream Thufir content JSON path for a session stamp (YYYYMMDD)."""
    return THUFIR_CONTENT_DIR / f"dossier_content_{stamp}.json"


def evidence_path(stamp: str) -> Path:
    """Return the evidence JSON path for a session stamp (YYYYMMDD)."""
    return EVIDENCE_DIR / f"credit_evidence_{stamp}.json"


def quotes_path(stamp: str) -> Path:
    """Return the sealed FMP credit proxy quotes JSON path for a session stamp (YYYYMMDD)."""
    return EVIDENCE_DIR / f"credit_quotes_{stamp}.json"


def nbfi_bdc_path(stamp: str) -> Path:
    """Return the sealed FRED NDFI/OAS & SEC EDGAR BDC PIK JSON path (G4 + G3)."""
    return EVIDENCE_DIR / f"credit_nbfi_bdc_{stamp}.json"


def clo_tranches_path(stamp: str) -> Path:
    """Return the sealed SEC EDGAR Form NPORT-P CLO tranche & trustee drop-in JSON path (G1)."""
    return EVIDENCE_DIR / f"credit_clo_tranches_{stamp}.json"


def court_dockets_path(stamp: str) -> Path:
    """Return the sealed UK Case Law Part 26A & SEC EFTS restructuring dockets JSON path (G2)."""
    return EVIDENCE_DIR / f"credit_court_dockets_{stamp}.json"


def bond_isins_path(stamp: str) -> Path:
    """Return the sealed European exchange Eurobond ISIN clean bid-ask marks JSON path (G5)."""
    return EVIDENCE_DIR / f"credit_bond_isins_{stamp}.json"


def vectors_path(stamp: str) -> Path:
    """Return the emitted alpha-g StructuredCreditSignalRecord JSON path for a session stamp (YYYYMMDD)."""
    return VECTORS_DIR / f"credit_vectors_{stamp}.json"


def output_path(stamp: str) -> Path:
    """Return the rendered dossier path for a session stamp (YYYYMMDD)."""
    return OUTPUT_DIR / f"Ops_Structured_Credit_CLO_Horizon_Dossier_{stamp}.html"


def load_json(path: Path) -> Any:
    """Read a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    """Write UTF-8 JSON atomically with stable formatting (non-ASCII preserved)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict]:
    """Return the structured-credit source registry keyed by source_id."""
    return {entry["source_id"]: entry for entry in load_json(path)}


def load_watchlist(path: Path = WATCHLIST_PATH) -> dict[str, Any]:
    """Return the canonical ISIN, FRED, BDC, CLO ETF and docket watchlist."""
    return load_json(path)


def prior_content(stamp: str, content_dir: Path = CONTENT_DIR) -> dict[str, Any] | None:
    """Return the most recent content JSON published before `stamp`, or None (freshness baseline)."""
    earlier = sorted(p for p in content_dir.glob("credit_content_*.json")
                     if p.stem.rsplit("_", 1)[-1] < stamp)
    return load_json(earlier[-1]) if earlier else None


def load_provider_key(provider: str, field: str = "api_key", path: Path = CREDENTIALS_PATH) -> str:
    """Load an API credential from sgc/config/credentials.toml without hardcoding secrets."""
    if not path.exists():
        raise FileNotFoundError(f"Credentials file missing at {path}")
    raw = path.read_text(encoding="utf-8")
    if tomllib is not None:
        data = tomllib.loads(raw)
        prov = data.get("providers", {}).get(provider, {})
        val = str(prov.get(field) or "").strip()
    else:
        import configparser
        cp = configparser.ConfigParser()
        cp.read_string(raw)
        sec = f"providers.{provider}"
        val = cp.get(sec, field, fallback="").strip().strip('"').strip("'")
    if not val:
        raise RuntimeError(f"Provider '{provider}.{field}' not configured in {path}")
    return val


def dec_round(val: Decimal | str | int | float, places: str = "0.01") -> float:
    """Quantize via Decimal ROUND_HALF_UP and convert to JSON-serializable float."""
    d = val if isinstance(val, Decimal) else Decimal(str(val))
    return float(d.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def sha256_text(text: str) -> str:
    """SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """SHA-256 hex digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_payload(payload: dict[str, Any]) -> str:
    """Compute canonical SHA-256 digest over a JSON dict excluding its top-level 'sha256' key."""
    body = {k: v for k, v in payload.items() if k != "sha256"}
    return sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=False))


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp ending in 'Z'."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def parse_as_of(value: str) -> date:
    """Parse an as-of stamp: YYYY-MM-DD, YYYY-MM or YYYY (partial stamps resolve to the first day)."""
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable as_of '{value}'")
