"""Incremental chunk validator and content assembler for Chrizza's credit dossier (v5).

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (operator intelligence publishing)
    Classifier    : CC-Bear · RC-Butterfly with roc/scripts/ops_chrizza/ops_chrizza_pre_publish_guard.py
    Lock status   : UNLOCKED — awaiting Agent Manager ratification

Why this exists:
    Writing a 900-line `credit_content_<YYYYMMDD>.json` in a single LLM tool call invites
    silent bare-number leaks, missing figure tokens, and late-stage re-generation. This
    builder decomposes each edition's content into four small, independently guarded JSON
    fragments under `roc/scripts/ops_chrizza/content/fragments/<YYYYMMDD>/`:
        * `figures.json` — the `F01..Fnn` figure registry
        * `brief.json`   — the Tab 0 Command Brief (`regime_label`, `pulse`, `decisions`, etc.)
        * `topics.json`  — Tabs 1–6 topic objects (or `topics_*.json` sub-chunks)
        * `tail.json`    — edition `meta`, `credit_vectors`, `calls`, `gaps`, `bibliography`, `heuristics`

CLI:
    python ops_chrizza_content_builder.py split       --date YYYYMMDD [--fragments-dir PATH]
    python ops_chrizza_content_builder.py check-chunk --date YYYYMMDD [--chunk all|figures|brief|topics|tail]
    python ops_chrizza_content_builder.py assemble    --date YYYYMMDD [--fragments-dir PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ops_chrizza_dossier_common import (  # noqa: E402
    SCHEMA_CONTENT,
    content_path,
    evidence_path,
    fragments_dir,
    load_json,
    load_registry,
    parse_utc,
    prior_content,
    save_json,
)
from ops_chrizza_learning_ledger import load_ledger  # noqa: E402
from ops_chrizza_pre_publish_guard import (  # noqa: E402
    PULSE_LABEL_MAX_CHARS,
    PULSE_VALUE_MAX_CHARS,
    _scan_prose,
    check_calls,
    check_content,
    check_figures,
    check_freshness,
    check_topics,
    check_vectors,
)

META_KEYS = ("dossier_id", "title", "author", "audience", "observed_at_utc", "session_for")
BRIEF_REQUIRED = (
    "regime_label", "regime_score_fig", "headline", "summary", "pulse", "decisions",
    "opportunities", "vetoes", "calendar", "mermaid",
)
CHUNKS = ("all", "figures", "brief", "topics", "tail")


def _load_topics_from_dir(fdir: Path) -> list[dict[str, Any]]:
    """Load `topics.json`, or concatenate sorted `topics_*.json` sub-chunks if `topics.json` is absent."""
    single = fdir / "topics.json"
    if single.exists():
        data = load_json(single)
        if not isinstance(data, list):
            raise ValueError(f"{single}: expected a JSON list of topic objects")
        return data
    parts = sorted(fdir.glob("topics_*.json"))
    if not parts:
        raise FileNotFoundError(f"{fdir}: neither topics.json nor topics_*.json found")
    topics: list[dict[str, Any]] = []
    for p in parts:
        chunk = load_json(p)
        if not isinstance(chunk, list):
            raise ValueError(f"{p}: expected a JSON list of topic objects")
        topics.extend(chunk)
    return topics


def split_content(stamp: str, *, fdir: Path | None = None, cpath: Path | None = None) -> Path:
    """Split an existing `credit_content_<YYYYMMDD>.json` into four canonical fragments."""
    src = cpath or content_path(stamp)
    target = fdir or fragments_dir(stamp)
    doc = load_json(src)
    target.mkdir(parents=True, exist_ok=True)
    save_json(target / "figures.json", doc["figures"])
    save_json(target / "brief.json", doc["brief"])
    save_json(target / "topics.json", doc["topics"])
    tail = {
        "meta": {k: doc[k] for k in META_KEYS},
        "credit_vectors": doc.get("credit_vectors", []),
        "calls": doc.get("calls", []),
        "gaps": doc.get("gaps", []),
        "bibliography": doc.get("bibliography", []),
        "heuristics": doc.get("heuristics", []),
    }
    save_json(target / "tail.json", tail)
    return target


def check_fragments(
    stamp: str,
    *,
    chunk: str = "all",
    fdir: Path | None = None,
    ev_doc: dict[str, Any] | None = None,
    prior_doc: dict[str, Any] | None = None,
) -> list[str]:
    """Validate one or all fragments against the pre-publish guard rules before assembly."""
    if chunk not in CHUNKS:
        raise ValueError(f"chunk must be one of {CHUNKS}")
    target = fdir or fragments_dir(stamp)
    fig_path = target / "figures.json"
    if not fig_path.exists():
        return [f"fragments: missing {fig_path}"]
    figures = load_json(fig_path)
    evidence = ev_doc if ev_doc is not None else load_json(evidence_path(stamp))
    evidence_ids = {i.get("id") for i in evidence.get("items", [])}

    tail_path = target / "tail.json"
    tail = load_json(tail_path) if tail_path.exists() else {}
    obs_str = (tail.get("meta") or {}).get("observed_at_utc") or evidence.get("observed_at_utc") or ""
    try:
        observed = parse_utc(obs_str)
    except ValueError:
        return [f"fragments: invalid or missing observed_at_utc '{obs_str}'"]

    defects: list[str] = []
    if chunk in ("all", "figures"):
        defects += check_figures(figures, evidence_ids, observed)

    if chunk in ("all", "brief"):
        bpath = target / "brief.json"
        if not bpath.exists():
            defects.append(f"fragments: missing {bpath}")
        else:
            brief = load_json(bpath)
            _scan_prose(brief, None, "content.brief", figures, defects)
            for key in BRIEF_REQUIRED:
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
                        f"{PULSE_LABEL_MAX_CHARS}-char KPI card header limit"
                    )
                if pfig_id not in figures:
                    defects.append(f"brief.pulse: figure {pfig_id} not defined")
                else:
                    pdisp = str(figures[pfig_id].get("display") or "")
                    if len(pdisp) > PULSE_VALUE_MAX_CHARS or "(" in pdisp or ";" in pdisp:
                        defects.append(
                            f"brief.pulse[{plabel}]: figure {pfig_id} display '{pdisp}' ({len(pdisp)} chars) "
                            f"exceeds {PULSE_VALUE_MAX_CHARS}-char KPI headline limit or contains parenthetical/semicolon"
                        )

    if chunk in ("all", "topics"):
        try:
            topics = _load_topics_from_dir(target)
        except (FileNotFoundError, ValueError) as exc:
            defects.append(f"fragments: {exc}")
        else:
            gap_ids = {g.get("id") for g in tail.get("gaps", [])} or {"G1", "G2", "G3", "G4", "G5"}
            prior = prior_doc if prior_doc is not None else prior_content(stamp)
            doc_stub = {"figures": figures, "topics": topics}
            _scan_prose({"topics": topics}, None, "content", figures, defects)
            defects += check_topics(doc_stub, evidence_ids, gap_ids)
            defects += check_freshness(doc_stub, evidence, observed, prior)

    if chunk in ("all", "tail"):
        if not tail_path.exists():
            defects.append(f"fragments: missing {tail_path}")
        else:
            meta = tail.get("meta") or {}
            for key in META_KEYS:
                if not meta.get(key):
                    defects.append(f"tail.meta: missing {key}")
            try:
                topics = _load_topics_from_dir(target)
            except (FileNotFoundError, ValueError):
                topics = []
            doc_stub = {
                "figures": figures,
                "topics": topics,
                "credit_vectors": tail.get("credit_vectors", []),
                "calls": tail.get("calls", []),
            }
            _scan_prose(
                {k: tail.get(k, []) for k in ("gaps", "bibliography", "heuristics")},
                None,
                "content",
                figures,
                defects,
            )
            defects += check_vectors(doc_stub, evidence_ids)
            defects += check_calls(doc_stub, load_ledger(), observed)
            registry = load_registry()
            for entry in tail.get("bibliography", []):
                if entry.get("candidate"):
                    if not entry.get("domain"):
                        defects.append("bibliography: candidate source needs a domain")
                elif entry.get("source_id") not in registry:
                    defects.append(f"bibliography: source_id '{entry.get('source_id')}' not in the registry")
    return defects


def assemble_content(
    stamp: str,
    *,
    fdir: Path | None = None,
    out: Path | None = None,
    ev_doc: dict[str, Any] | None = None,
    prior_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble and guard a full `credit_content_<YYYYMMDD>.json` from its validated fragments."""
    target = fdir or fragments_dir(stamp)
    defects = check_fragments(stamp, chunk="all", fdir=target, ev_doc=ev_doc, prior_doc=prior_doc)
    if defects:
        raise ValueError("Fragment guard failed:\n" + "\n".join(f"  ✗ {d}" for d in defects))

    figures = load_json(target / "figures.json")
    brief = load_json(target / "brief.json")
    topics = _load_topics_from_dir(target)
    tail = load_json(target / "tail.json")
    meta = tail["meta"]
    content: dict[str, Any] = {
        "schema": SCHEMA_CONTENT,
        **{k: meta[k] for k in META_KEYS},
        "figures": figures,
        "brief": brief,
        "credit_vectors": tail.get("credit_vectors", []),
        "topics": topics,
        "calls": tail.get("calls", []),
        "gaps": tail.get("gaps", []),
        "bibliography": tail.get("bibliography", []),
        "heuristics": sorted(tail.get("heuristics", []), key=lambda h: str(h.get("id", ""))),
    }
    evidence = ev_doc if ev_doc is not None else load_json(evidence_path(stamp))
    prior = prior_doc if prior_doc is not None else prior_content(stamp)
    full_defects = check_content(content, evidence, load_registry(), load_ledger(), prior)
    if full_defects:
        raise ValueError("Assembled content guard failed:\n" + "\n".join(f"  ✗ {d}" for d in full_defects))

    dest = out or content_path(stamp)
    save_json(dest, content)
    return content


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Chrizza dossier chunk validator & content assembler")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_split = sub.add_parser("split", help="split credit_content_<YYYYMMDD>.json into fragments")
    p_split.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    p_split.add_argument("--fragments-dir", type=Path, help="override fragments directory")

    p_check = sub.add_parser("check-chunk", help="validate one or all fragments before assembly")
    p_check.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    p_check.add_argument("--chunk", default="all", choices=CHUNKS, help="fragment to validate")
    p_check.add_argument("--fragments-dir", type=Path, help="override fragments directory")

    p_asm = sub.add_parser("assemble", help="guard and merge fragments into credit_content_<YYYYMMDD>.json")
    p_asm.add_argument("--date", required=True, help="session stamp YYYYMMDD")
    p_asm.add_argument("--fragments-dir", type=Path, help="override fragments directory")
    p_asm.add_argument("--out", type=Path, help="override output content JSON path")

    args = parser.parse_args(argv)
    if args.cmd == "split":
        out_dir = split_content(args.date, fdir=args.fragments_dir)
        print(f"split {args.date} -> {out_dir}")
        return 0
    if args.cmd == "check-chunk":
        defects = check_fragments(args.date, chunk=args.chunk, fdir=args.fragments_dir)
        for d in defects:
            print(f"  ✗ {d}")
        print(f"{'FAIL' if defects else 'PASS'} — {len(defects)} defect(s) [chunk={args.chunk}, {args.date}]")
        return 1 if defects else 0
    if args.cmd == "assemble":
        try:
            doc = assemble_content(args.date, fdir=args.fragments_dir, out=args.out)
        except ValueError as exc:
            print(str(exc))
            return 1
        dest = args.out or content_path(args.date)
        print(
            f"PASS — assembled {dest} ({len(doc['figures'])} figures, "
            f"{len(doc['topics'])} topics, {len(doc['calls'])} calls)"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

