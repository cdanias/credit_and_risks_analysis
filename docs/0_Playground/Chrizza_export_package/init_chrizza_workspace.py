"""Portable workspace packer and installer for Chrizza (structured-credit-agent).

RAD*ICAL Code_Header
    Code_Author   : Chrizza (structured-credit-agent)
    Service-Type  : P-Series support (portable agent packaging & target workspace bootstrap)
    Classifier    : CC-Bear · RC-Butterfly
    Lock status   : UNLOCKED — awaiting Agent Manager ratification

Purpose:
    Packages Chrizza's complete operational genome, memory (MEM-JOGs), workflow,
    Python dossier engine, fail-closed pre-publish guard, incremental chunk builder,
    v4 statutory/exchange data-gap sweepers, call ledger, source/watchlist registries,
    canonical & runtime HTML templates, reference HTML dossiers, and brand SVG assets
    into a self-contained export bundle (`payload/` + `PACKAGE_MANIFEST.json`), and
    installs them into any target workspace directory (regardless of workspace root name).

CLI Usage (on the target machine):
    # 1. Verify package SHA-256 integrity before installing:
    python init_chrizza_workspace.py verify-package

    # 2. Install into a target workspace root and run full self-test (guard + pytest):
    python init_chrizza_workspace.py install --target /path/to/new_workspace --verify

    # 3. Preview installation without writing files:
    python init_chrizza_workspace.py install --target /path/to/new_workspace --dry-run

CLI Usage (on the source machine to refresh the export package):
    python init_chrizza_workspace.py pack
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
PAYLOAD_DIR = PACKAGE_DIR / "payload"
MANIFEST_PATH = PACKAGE_DIR / "PACKAGE_MANIFEST.json"

# Source workspace root when running `pack` inside SGIP_Investing/DOCS/1_playground/Chrizza_export_package
SOURCE_ROOT = PACKAGE_DIR.parents[2]

OLD_FILE_URI_RE = re.compile(
    r"file:///[A-Za-z]:/Dev/Antigravity_Agents/SGIP_Investing/",
    re.IGNORECASE,
)

CREDENTIALS_EXAMPLE = """# SGC / Chrizza Structured Credit Telemetry Credentials
# Copy this file to `sgc/config/credentials.toml` and populate your API keys
# before running live `sweep-quotes` (FMP) or `ops_chrizza_sweep_nbfi_and_bdc.py` (FRED).
# Note: SEC EDGAR (10-Q XBRL, Form NPORT-P, EFTS), UK High Court Case Law XML,
# and Frankfurt/Stuttgart Eurobond ISIN sweeps require NO API key.

[providers.fmp]
api_key = "YOUR_FMP_API_KEY_HERE"

[providers.fred]
api_key = "YOUR_FRED_API_KEY_HERE"
"""

EMPTY_DIRS = (
    "roc/scripts/ops_chrizza/inbox/trustee",
    "roc/scripts/ops_chrizza/inbox/dockets",
    "roc/DOCS/comms/chrizza/1_inbox",
    "roc/DOCS/comms/chrizza/2_in-progress",
    "roc/DOCS/comms/chrizza/3_archive",
)


def sha256_bytes(data: bytes) -> str:
    """Return hex SHA-256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file."""
    return sha256_bytes(path.read_bytes())


def discover_source_files(src_root: Path) -> list[tuple[str, str]]:
    """Return sorted list of (relative_posix_path, category) to include in the export package."""
    items: list[tuple[str, str]] = []

    def add(rel: str, category: str) -> None:
        p = src_root / rel
        if not p.exists():
            raise FileNotFoundError(f"Required export artefact missing at {p}")
        items.append((Path(rel).as_posix(), category))

    # 1. Agent Genome, Character Substrate, MEM-JOGs & Workflows (.agent/)
    add(".agent/skills/structured-credit-agent/SKILL.md", "agent_genome")
    for mj in sorted((src_root / ".agent/skills/structured-credit-agent").glob("MEM-JOG-*.md")):
        add(mj.relative_to(src_root).as_posix(), "mem_jog")
    add(".agent/skills/character-substrate/SKILL.md", "character_substrate")
    add(".agent/workflows/operate-chrizza-structured-credit-dossier-report.md", "workflow")
    if (src_root / ".agent/workflows/create-mem-jog.md").exists():
        add(".agent/workflows/create-mem-jog.md", "workflow")

    # 2. Registries & Watchlists (roc/config/)
    add("roc/config/structured_credit_intelligence_sources.json", "config_registry")
    add("roc/config/structured_credit_isin_watchlist.json", "config_watchlist")

    # 3. Core Python Engine, Guard, Builder, Sweepers, Ledger & Tests (roc/scripts/ops_chrizza/)
    ops_dir = src_root / "roc/scripts/ops_chrizza"
    for py in sorted(ops_dir.glob("*.py")):
        add(py.relative_to(src_root).as_posix(), "ops_script")
    add("roc/scripts/ops_chrizza/chrizza_call_ledger.json", "call_ledger")
    add(
        "roc/scripts/ops_chrizza/templates/Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html",
        "template_mirror",
    )

    # 4. Sealed Content, Fragments, Evidence & Vectors (roc/scripts/ops_chrizza/{content,evidence,vectors}/)
    for cfile in sorted((ops_dir / "content").glob("credit_content_*.json")):
        add(cfile.relative_to(src_root).as_posix(), "dossier_content")
    for frag in sorted((ops_dir / "content/fragments").rglob("*.json")):
        add(frag.relative_to(src_root).as_posix(), "dossier_fragment")
    for efile in sorted((ops_dir / "evidence").glob("credit_*.json")):
        add(efile.relative_to(src_root).as_posix(), "sealed_evidence")
    for vfile in sorted((ops_dir / "vectors").glob("credit_vectors_*.json")):
        add(vfile.relative_to(src_root).as_posix(), "emitted_vectors")

    # 5. Canonical Master Template & Reference HTML Dossiers (DOCS/4_operate/)
    add(
        "DOCS/4_operate/templates/Ops_Structured_Credit_CLO_Horizon_Dossier_Template.html",
        "template_canonical",
    )
    for hfile in sorted((src_root / "DOCS/4_operate").glob("Ops_Structured_Credit_CLO_Horizon_Dossier_*.html")):
        add(hfile.relative_to(src_root).as_posix(), "reference_dossier_html")

    # 6. Cross-Tree Brand SVG Assets & Supporting Persona/Philosophy Docs
    add("sgc/crates/sgc-app/ui/src/assets/infinix-brand-logo.svg", "brand_asset")
    add("sgc/crates/sgc-app/ui/src/app/sgc-top-status-bar.ts", "brand_asset")
    for extra, cat in (
        ("roc/DOCS/assets/images/chrizza_v1.png", "persona_asset"),
        ("roc/DOCS/assets/images/chrizza_motif_v1.png", "persona_asset"),
        ("roc/DOCS/reports/Job_and_Persona_Spec_Chrizza_Structured_Credit_CLO_Specialist.md", "persona_spec"),
        ("roc/DOCS/reports/Chrizza_CLO_Mezzanine_BBB_and_BB_Signal_Triggers_20261026.html", "reference_report"),
    ):
        if (src_root / extra).exists():
            add(extra, cat)

    return items


def relativize_markdown_links(text: str) -> str:
    """Replace hardcoded SGIP_Investing file:/// URIs in markdown with workspace-relative paths."""
    return OLD_FILE_URI_RE.sub("", text)


def pack_export_bundle(src_root: Path = SOURCE_ROOT) -> dict[str, Any]:
    """Copy all Chrizza artefacts into `payload/`, sanitize markdown links, and write `PACKAGE_MANIFEST.json`."""
    if PAYLOAD_DIR.exists():
        shutil.rmtree(PAYLOAD_DIR)
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    discovered = discover_source_files(src_root)
    manifest_files: list[dict[str, Any]] = []

    for rel_posix, category in discovered:
        src_path = src_root / rel_posix
        dst_path = PAYLOAD_DIR / rel_posix
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.suffix.lower() == ".md":
            raw_text = src_path.read_text(encoding="utf-8")
            cleaned = relativize_markdown_links(raw_text)
            dst_path.write_text(cleaned, encoding="utf-8", newline="\n")
        else:
            shutil.copy2(src_path, dst_path)

        manifest_files.append({
            "path": rel_posix,
            "category": category,
            "size_bytes": dst_path.stat().st_size,
            "sha256": sha256_file(dst_path),
        })

    # Write sanitized credentials.toml.example (never export live API keys)
    cred_example_rel = "sgc/config/credentials.toml.example"
    cred_example_dst = PAYLOAD_DIR / cred_example_rel
    cred_example_dst.parent.mkdir(parents=True, exist_ok=True)
    cred_example_dst.write_text(CREDENTIALS_EXAMPLE, encoding="utf-8", newline="\n")
    manifest_files.append({
        "path": cred_example_rel,
        "category": "config_credentials_template",
        "size_bytes": cred_example_dst.stat().st_size,
        "sha256": sha256_file(cred_example_dst),
    })

    # Create empty inbox/comms directories with .gitkeep
    for empty_rel in EMPTY_DIRS:
        keep_rel = f"{empty_rel}/.gitkeep"
        keep_dst = PAYLOAD_DIR / keep_rel
        keep_dst.parent.mkdir(parents=True, exist_ok=True)
        keep_dst.write_text("", encoding="utf-8")
        manifest_files.append({
            "path": keep_rel,
            "category": "directory_scaffold",
            "size_bytes": 0,
            "sha256": sha256_file(keep_dst),
        })

    manifest_files.sort(key=lambda x: x["path"])
    manifest_body = {
        "schema": "chrizza.export_package.v1",
        "agent": "Chrizza (structured-credit-agent)",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "relative_root_contract": "All paths are workspace-relative; no dependency on 'SGIP_Investing' folder name.",
        "total_files": len(manifest_files),
        "total_bytes": sum(f["size_bytes"] for f in manifest_files),
        "files": manifest_files,
    }
    manifest_body["package_sha256"] = sha256_bytes(
        json.dumps(manifest_body["files"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    MANIFEST_PATH.write_text(json.dumps(manifest_body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_body


def verify_package() -> list[str]:
    """Verify every file in `payload/` against `PACKAGE_MANIFEST.json`."""
    if not MANIFEST_PATH.exists():
        return [f"Missing manifest: {MANIFEST_PATH}"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    defects: list[str] = []
    expected_pkg_sha = sha256_bytes(
        json.dumps(manifest.get("files", []), sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    if manifest.get("package_sha256") != expected_pkg_sha:
        defects.append("PACKAGE_MANIFEST.json top-level package_sha256 mismatch")

    for entry in manifest.get("files", []):
        rel = entry["path"]
        p = PAYLOAD_DIR / rel
        if not p.exists():
            defects.append(f"missing payload file: {rel}")
            continue
        actual_sha = sha256_file(p)
        if actual_sha != entry["sha256"]:
            defects.append(f"sha256 mismatch on {rel}: expected {entry['sha256'][:12]}…, got {actual_sha[:12]}…")
    return defects


def install_to_target(
    target_root: Path,
    *,
    dry_run: bool = False,
    verify: bool = False,
) -> int:
    """Install `payload/` into `target_root` and optionally run guard + pytest verification."""
    pkg_defects = verify_package()
    if pkg_defects:
        for d in pkg_defects:
            print(f"  ✗ {d}")
        print(f"FAIL — export package integrity check failed ({len(pkg_defects)} defect(s))")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    target_root = target_root.resolve()
    print(f"{'[DRY-RUN] ' if dry_run else ''}Installing Chrizza export package -> {target_root}")

    installed = 0
    for entry in manifest["files"]:
        rel = entry["path"]
        src = PAYLOAD_DIR / rel
        dst = target_root / rel
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        installed += 1

    # Scaffold sgc/config/credentials.toml from example if absent
    cred_target = target_root / "sgc/config/credentials.toml"
    cred_example = target_root / "sgc/config/credentials.toml.example"
    if not cred_target.exists():
        if not dry_run and cred_example.exists():
            cred_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cred_example, cred_target)
        print(f"  + scaffolded {cred_target.relative_to(target_root).as_posix()} (populate FMP/FRED keys before live sweeps)")

    print(f"Installed {installed} artefact(s) across relative workspace tree.")
    if dry_run or not verify:
        return 0

    print("\nRunning post-install verification in target workspace…")
    cmds = [
        [
            sys.executable,
            str(target_root / "roc/scripts/ops_chrizza/ops_chrizza_generate_credit_dossier.py"),
            "sync-template",
        ],
        [
            sys.executable,
            str(target_root / "roc/scripts/ops_chrizza/ops_chrizza_pre_publish_guard.py"),
            "--date",
            "20261107",
            "--html",
            str(target_root / "DOCS/4_operate/Ops_Structured_Credit_CLO_Horizon_Dossier_20261107.html"),
        ],
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=str(target_root), check=False)
        if proc.returncode != 0:
            print(f"FAIL — verification command exited with code {proc.returncode}: {' '.join(cmd)}")
            return proc.returncode

    import importlib.util
    test_file = target_root / "roc/scripts/ops_chrizza/test_ops_chrizza_dossier.py"
    if importlib.util.find_spec("pytest") is not None:
        proc = subprocess.run([sys.executable, "-m", "pytest", str(test_file), "-q"], cwd=str(target_root), check=False)
        if proc.returncode != 0:
            print(f"FAIL — pytest exited with code {proc.returncode}")
            return proc.returncode
    else:
        rc = _run_pytest_fallback(test_file, target_root)
        if rc != 0:
            return rc

    print("PASS — Target workspace verified (template synced, 20261107 guard 0 defects, full pytest green).")
    return 0


def _run_pytest_fallback(test_file: Path, target_root: Path) -> int:
    """Execute test_ops_chrizza_dossier.py when pytest package is not installed in system Python."""
    import inspect
    import tempfile
    import types

    pytest_mod = types.ModuleType("pytest")

    def fixture():
        def dec(fn):
            fn._is_fixture = True
            return fn
        return dec

    class Mark:
        @staticmethod
        def parametrize(argnames, argvalues):
            names = [a.strip() for a in argnames.split(",")]
            def dec(fn):
                fn._parametrize = (names, argvalues)
                return fn
            return dec

    class Approx:
        def __init__(self, val, rel=1e-6, abs=1e-12):
            self.val, self.rel, self.abs = val, rel, abs
        def __eq__(self, other):
            return abs(other - self.val) <= max(self.rel * abs(self.val), self.abs)

    class RaisesCtx:
        def __init__(self, exc):
            self.exc = exc
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, tb):
            if exc_type is None:
                raise AssertionError(f"Expected {self.exc}, but no exception was raised")
            return issubclass(exc_type, self.exc)

    pytest_mod.fixture = fixture
    pytest_mod.mark = Mark()
    pytest_mod.approx = Approx
    pytest_mod.raises = RaisesCtx
    sys.modules["pytest"] = pytest_mod

    sys.path.insert(0, str(test_file.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_ops_chrizza_dossier", test_file)
    tmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tmod)

    fixtures = {
        name: fn
        for name, fn in inspect.getmembers(tmod, inspect.isfunction)
        if getattr(fn, "_is_fixture", False)
    }
    passed = 0
    for name, fn in inspect.getmembers(tmod, inspect.isfunction):
        if not name.startswith("test_"):
            continue
        sig = inspect.signature(fn)
        if hasattr(fn, "_parametrize"):
            pnames, pvals = fn._parametrize
            for row in pvals:
                if not isinstance(row, tuple):
                    row = (row,)
                kwargs = dict(zip(pnames, row))
                for p in sig.parameters:
                    if p not in kwargs and p in fixtures:
                        kwargs[p] = fixtures[p]()
                fn(**kwargs)
                passed += 1
        else:
            with tempfile.TemporaryDirectory() as td:
                kwargs = {}
                for p in sig.parameters:
                    if p == "tmp_path":
                        kwargs[p] = Path(td)
                    elif p in fixtures:
                        kwargs[p] = fixtures[p]()
                fn(**kwargs)
                passed += 1
    print(f"{passed} passed (pytest fallback runner)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Chrizza portable export package builder & workspace installer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("pack", help="build/refresh payload/ and PACKAGE_MANIFEST.json from source workspace")
    sub.add_parser("verify-package", help="verify SHA-256 of all files in payload/ against PACKAGE_MANIFEST.json")

    p_inst = sub.add_parser("install", help="install Chrizza into a target workspace directory")
    p_inst.add_argument("--target", type=Path, required=True, help="target workspace root directory")
    p_inst.add_argument("--dry-run", action="store_true", help="preview files to be installed without writing")
    p_inst.add_argument("--verify", action="store_true", help="run sync-template, guard, and pytest in target workspace")

    args = parser.parse_args(argv)
    if args.cmd == "pack":
        manifest = pack_export_bundle(SOURCE_ROOT)
        print(
            f"PACKED — {manifest['total_files']} files ({manifest['total_bytes']:,} bytes) "
            f"into {PAYLOAD_DIR} [package_sha256={manifest['package_sha256'][:16]}…]"
        )
        return 0
    if args.cmd == "verify-package":
        defects = verify_package()
        for d in defects:
            print(f"  ✗ {d}")
        print(f"{'FAIL' if defects else 'PASS'} — {len(defects)} defect(s) in export package")
        return 1 if defects else 0
    if args.cmd == "install":
        return install_to_target(args.target, dry_run=args.dry_run, verify=args.verify)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

