"""
GRC Compliance Gap Analyzer — Phase 1
NIST SP 800-53 Rev 5 JSON Parser and Control Database Builder

This module:
  1. Downloads the official NIST SP 800-53 Rev 5 JSON from the NIST GitHub repo
  2. Parses and normalizes the control catalog into a clean data model
  3. Stores everything in a local SQLite database for fast querying
  4. Exposes a ControlDatabase class used by all later phases

Author: GRC Analyzer
NIST Source: https://github.com/usnistgov/oscal-content (public domain)
"""

import json
import sqlite3
import pathlib
import textwrap
import urllib.request
import urllib.error
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Where to store project data files (relative to this file's parent)
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
DB_PATH      = DATA_DIR / "nist_80053.db"
JSON_PATH    = DATA_DIR / "nist_80053_rev5.json"

# Official NIST SP 800-53 Rev 5 OSCAL JSON — public domain, no API key needed.
# This is the "catalog" format from NIST's official OSCAL content repository.
NIST_JSON_URL = (
    "https://raw.githubusercontent.com/usnistgov/oscal-content/main/"
    "nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
)

# ── NIST control families for display / filtering ──────────────────────────
CONTROL_FAMILIES = {
    "AC": "Access Control",
    "AT": "Awareness and Training",
    "AU": "Audit and Accountability",
    "CA": "Assessment, Authorization, and Monitoring",
    "CM": "Configuration Management",
    "CP": "Contingency Planning",
    "IA": "Identification and Authentication",
    "IR": "Incident Response",
    "MA": "Maintenance",
    "MP": "Media Protection",
    "PE": "Physical and Environmental Protection",
    "PL": "Planning",
    "PM": "Program Management",
    "PS": "Personnel Security",
    "PT": "PII Processing and Transparency",
    "RA": "Risk Assessment",
    "SA": "System and Services Acquisition",
    "SC": "System and Communications Protection",
    "SI": "System and Information Integrity",
    "SR": "Supply Chain Risk Management",
}


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------

def download_nist_json(force_refresh: bool = False) -> pathlib.Path:
    """
    Download the NIST SP 800-53 Rev 5 OSCAL JSON catalog.

    Args:
        force_refresh: Re-download even if the file already exists locally.

    Returns:
        Path to the local JSON file.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if JSON_PATH.exists() and not force_refresh:
        print(f"[✓] NIST JSON already cached at: {JSON_PATH}")
        return JSON_PATH

    print(f"[→] Downloading NIST SP 800-53 Rev 5 from NIST GitHub...")
    print(f"    URL: {NIST_JSON_URL}")

    try:
        # urllib is stdlib — no requests dependency needed
        with urllib.request.urlopen(NIST_JSON_URL, timeout=30) as response:
            raw = response.read()

        JSON_PATH.write_bytes(raw)
        size_kb = len(raw) / 1024
        print(f"[✓] Downloaded {size_kb:.1f} KB → {JSON_PATH}")
        return JSON_PATH

    except urllib.error.URLError as exc:
        print(f"[✗] Download failed: {exc}")
        print("    Please download manually from:")
        print(f"    {NIST_JSON_URL}")
        print(f"    and save it to: {JSON_PATH}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# OSCAL parser — translate NIST's OSCAL JSON into our internal model
# ---------------------------------------------------------------------------

def _extract_prose(parts: list[dict], accumulated: list[str] | None = None) -> str:
    """
    Recursively extract human-readable prose from an OSCAL 'parts' array.

    OSCAL parts are nested: a control's description is in parts[*].prose,
    and each part may have sub-parts with additional detail.

    Returns:
        A single newline-joined string of all prose fragments.
    """
    if accumulated is None:
        accumulated = []

    for part in parts:
        if prose := part.get("prose", "").strip():
            accumulated.append(prose)
        # Recurse into nested parts (e.g. assessment objectives)
        if sub_parts := part.get("parts", []):
            _extract_prose(sub_parts, accumulated)

    return "\n".join(accumulated)


def _extract_parameters(params: list[dict]) -> dict[str, str]:
    """
    Extract ODPs (Organization-Defined Parameters) from OSCAL param objects.

    NIST controls use parameters like {{ insert: param, ac-01_odp.01 }}
    to indicate where organizations fill in their own values.

    Returns:
        Dict mapping param_id → label string.
    """
    result = {}
    for param in params:
        param_id = param.get("id", "")
        # The human-readable label is in 'label'; fall back to select/values
        label = param.get("label", "")
        if not label:
            # Some params use 'select' (choice lists) instead of free-text labels
            select = param.get("select", {})
            choices = select.get("choice", [])
            label = " | ".join(choices) if choices else "(organization-defined)"
        result[param_id] = label
    return result


def _extract_references(links: list[dict]) -> list[str]:
    """
    Extract external reference URLs from an OSCAL links array.

    Returns:
        List of href strings (may be relative OSCAL fragment refs or URLs).
    """
    return [
        link.get("href", "")
        for link in links
        if link.get("rel") in ("reference", "related", None)
        and link.get("href", "")
    ]


def parse_oscal_catalog(json_path: pathlib.Path) -> list[dict]:
    """
    Parse the full NIST SP 800-53 OSCAL catalog into a flat list of controls.

    OSCAL structure (simplified):
        catalog
        └── groups[]          ← control families (AC, AU, ...)
            └── controls[]    ← base controls  (AC-1, AC-2, ...)
                └── controls[]  ← control enhancements (AC-2(1), AC-2(2), ...)

    Each control we emit has:
        control_id, family, title, description, discussion,
        parameters (JSON), related_controls, references, is_enhancement,
        parent_id, baseline_impact

    Returns:
        List of dicts, one per control/enhancement.
    """
    print(f"\n[→] Parsing OSCAL JSON from: {json_path}")
    raw = json.loads(json_path.read_text(encoding="utf-8"))

    catalog = raw.get("catalog", {})
    groups   = catalog.get("groups", [])

    all_controls: list[dict] = []

    for group in groups:
        # The group 'id' is the family code, e.g. "ac", "au"
        family_code = group.get("id", "").upper()
        family_name = group.get("title", CONTROL_FAMILIES.get(family_code, "Unknown"))

        for control in group.get("controls", []):
            # ── Parse the base control ──────────────────────────────────────
            record = _parse_single_control(
                control,
                family_code=family_code,
                family_name=family_name,
                is_enhancement=False,
                parent_id=None,
            )
            all_controls.append(record)

            # ── Parse enhancements (nested controls) ────────────────────────
            for enhancement in control.get("controls", []):
                enh_record = _parse_single_control(
                    enhancement,
                    family_code=family_code,
                    family_name=family_name,
                    is_enhancement=True,
                    parent_id=record["control_id"],
                )
                all_controls.append(enh_record)

    print(f"[✓] Parsed {len(all_controls)} controls and enhancements")
    return all_controls


def _parse_single_control(
    control: dict,
    family_code: str,
    family_name: str,
    is_enhancement: bool,
    parent_id: Optional[str],
) -> dict:
    """
    Transform a single OSCAL control object into our flat record format.
    """
    control_id = control.get("id", "").upper()
    title      = control.get("title", "")
    parts      = control.get("parts", [])
    params     = control.get("params", [])
    links      = control.get("links", [])
    props      = {p["name"]: p["value"] for p in control.get("props", [])}

    # ── Extract prose sections ──────────────────────────────────────────────
    # OSCAL separates "statement" (what to do) from "guidance" (discussion)
    description_parts = [p for p in parts if p.get("name") == "statement"]
    guidance_parts    = [p for p in parts if p.get("name") == "guidance"]

    description = _extract_prose(description_parts)
    discussion  = _extract_prose(guidance_parts)

    # ── Related controls (from links with rel="related") ───────────────────
    related = [
        link["href"].lstrip("#").upper()
        for link in links
        if link.get("rel") == "related"
    ]

    # ── References (external URLs) ─────────────────────────────────────────
    references = _extract_references(links)

    # ── Organization-defined parameters ────────────────────────────────────
    parameters = _extract_parameters(params)

    # ── Baseline impact (Low / Moderate / High) ────────────────────────────
    # Props may carry 'included-in-baseline' or similar — varies by OSCAL version
    baseline = props.get("included-in-baseline", "")

    return {
        "control_id":      control_id,
        "family_code":     family_code,
        "family_name":     family_name,
        "title":           title,
        "description":     description,
        "discussion":      discussion,
        "parameters":      json.dumps(parameters),   # stored as JSON string
        "related_controls": json.dumps(related),
        "references":      json.dumps(references),
        "is_enhancement":  int(is_enhancement),
        "parent_id":       parent_id,
        "baseline_impact": baseline,
    }


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

class ControlDatabase:
    """
    SQLite-backed database of NIST SP 800-53 controls.

    Used by all later phases:
      - Phase 3: LLM maps a finding → control_id via lookup
      - Phase 4: Risk scoring uses family and baseline_impact
      - Phase 5: Report generation queries full control details
      - Phase 6: LLM narrative pulls description + discussion

    Usage:
        db = ControlDatabase()
        ctrl = db.get_control("AC-2")
        results = db.search_controls("password")
        family  = db.get_family("IA")
    """

    def __init__(self, db_path: pathlib.Path = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ── Connection management ───────────────────────────────────────────────

    def connect(self) -> "ControlDatabase":
        """Open the database connection. Call this before any queries."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row   # enables dict-like access
        return self

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    # ── Schema creation ─────────────────────────────────────────────────────

    def create_schema(self):
        """
        Create the controls table and supporting indexes.
        Safe to call on an existing DB — uses IF NOT EXISTS.
        """
        assert self._conn, "Call connect() first"

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS controls (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                control_id      TEXT    NOT NULL UNIQUE,   -- e.g. "AC-2"
                family_code     TEXT    NOT NULL,           -- e.g. "AC"
                family_name     TEXT    NOT NULL,
                title           TEXT    NOT NULL,
                description     TEXT,                       -- statement prose
                discussion      TEXT,                       -- guidance prose
                parameters      TEXT,                       -- JSON dict of ODPs
                related_controls TEXT,                      -- JSON list
                "references"    TEXT,                       -- JSON list of hrefs
                is_enhancement  INTEGER NOT NULL DEFAULT 0, -- 1 if AC-2(1) etc.
                parent_id       TEXT,                       -- parent control_id
                baseline_impact TEXT                        -- Low/Mod/High if available
            );

            -- Enables fast family-level queries in Phase 3
            CREATE INDEX IF NOT EXISTS idx_family ON controls(family_code);

            -- Enables fast enhancement lookups in Phase 3
            CREATE INDEX IF NOT EXISTS idx_parent ON controls(parent_id);

            -- Full-text search table (title + description) for Phase 3 mapping
            CREATE VIRTUAL TABLE IF NOT EXISTS controls_fts USING fts5(
                control_id,
                title,
                description,
                discussion,
                content='controls',
                content_rowid='id'
            );
        """)
        self._conn.commit()

    def _rebuild_fts(self):
        """Populate the FTS index from the main controls table."""
        assert self._conn
        # For content= FTS tables, use INSERT with explicit rowids
        self._conn.execute("INSERT INTO controls_fts(controls_fts) VALUES('rebuild');")
        self._conn.commit()

    # ── Bulk load ───────────────────────────────────────────────────────────

    def load_controls(self, records: list[dict], rebuild_fts: bool = True):
        """
        Insert or replace all control records into the database.

        Args:
            records:     Output of parse_oscal_catalog().
            rebuild_fts: Whether to refresh the full-text search index.
        """
        assert self._conn

        self._conn.executemany("""
            INSERT OR REPLACE INTO controls (
                control_id, family_code, family_name, title, description,
                discussion, parameters, related_controls, "references",
                is_enhancement, parent_id, baseline_impact
            ) VALUES (
                :control_id, :family_code, :family_name, :title, :description,
                :discussion, :parameters, :related_controls, :references,
                :is_enhancement, :parent_id, :baseline_impact
            )
        """, records)
        self._conn.commit()

        if rebuild_fts:
            self._rebuild_fts()

        count = self._conn.execute("SELECT COUNT(*) FROM controls").fetchone()[0]
        print(f"[✓] Database loaded: {count} controls in {self.db_path}")

    # ── Query interface — used by Phase 3 / 5 / 6 ──────────────────────────

    def get_control(self, control_id: str) -> Optional[dict]:
        """
        Fetch a single control by exact ID (case-insensitive).

        Args:
            control_id: e.g. "AC-2" or "ac-2"

        Returns:
            Dict with all control fields, or None if not found.
        """
        assert self._conn
        row = self._conn.execute(
            "SELECT * FROM controls WHERE UPPER(control_id) = ?",
            (control_id.upper(),)
        ).fetchone()
        return dict(row) if row else None

    def get_family(self, family_code: str) -> list[dict]:
        """
        Return all base controls (not enhancements) for a control family.

        Args:
            family_code: e.g. "AC", "AU", "IA"

        Returns:
            List of control dicts sorted by control_id.
        """
        assert self._conn
        rows = self._conn.execute("""
            SELECT * FROM controls
            WHERE UPPER(family_code) = ?
              AND is_enhancement = 0
            ORDER BY control_id
        """, (family_code.upper(),)).fetchall()
        return [dict(r) for r in rows]

    def get_enhancements(self, parent_control_id: str) -> list[dict]:
        """
        Return all enhancements for a base control, e.g. AC-2(1), AC-2(2).

        Args:
            parent_control_id: e.g. "AC-2"

        Returns:
            List of enhancement dicts sorted by control_id.
        """
        assert self._conn
        rows = self._conn.execute("""
            SELECT * FROM controls
            WHERE UPPER(parent_id) = ?
            ORDER BY control_id
        """, (parent_control_id.upper(),)).fetchall()
        return [dict(r) for r in rows]

    def search_controls(
        self,
        query: str,
        limit: int = 10,
        family_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Full-text search over control titles, descriptions, and discussion.

        This is the primary interface for Phase 3's LLM-to-control mapping:
        given a finding like "no password complexity enforced", this returns
        the most relevant controls (IA-5, etc.).

        Args:
            query:         Free-text search string.
            limit:         Max results to return.
            family_filter: Restrict to a specific family code, e.g. "IA".

        Returns:
            List of matching control dicts, ordered by FTS relevance.
        """
        assert self._conn

        # FTS5 treats bare words as individual tokens and multi-word phrases
        # need quoting. Wrap the entire query in double-quotes to make it a
        # phrase search, or split and join as individual token searches.
        # We use the individual-token approach (AND logic) for better recall.
        fts_tokens = " AND ".join(
            f'"{word.strip()}"'
            for word in query.split()
            if word.strip()
        )

        try:
            if family_filter:
                rows = self._conn.execute("""
                    SELECT c.* FROM controls c
                    JOIN controls_fts fts ON c.id = fts.rowid
                    WHERE controls_fts MATCH ?
                      AND UPPER(c.family_code) = ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_tokens, family_filter.upper(), limit)).fetchall()
            else:
                rows = self._conn.execute("""
                    SELECT c.* FROM controls c
                    JOIN controls_fts fts ON c.id = fts.rowid
                    WHERE controls_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_tokens, limit)).fetchall()
        except sqlite3.OperationalError:
            # Fallback: LIKE search if FTS query is malformed
            like = f"%{query}%"
            rows = self._conn.execute("""
                SELECT * FROM controls
                WHERE title LIKE ? OR description LIKE ? OR discussion LIKE ?
                LIMIT ?
            """, (like, like, like, limit)).fetchall()

        return [dict(r) for r in rows]

    def list_families(self) -> list[dict]:
        """
        Return a summary of all control families with control counts.

        Returns:
            List of dicts: {family_code, family_name, total, base_controls, enhancements}
        """
        assert self._conn
        rows = self._conn.execute("""
            SELECT
                family_code,
                family_name,
                COUNT(*)                                AS total,
                SUM(CASE WHEN is_enhancement=0 THEN 1 ELSE 0 END) AS base_controls,
                SUM(CASE WHEN is_enhancement=1 THEN 1 ELSE 0 END) AS enhancements
            FROM controls
            GROUP BY family_code
            ORDER BY family_code
        """).fetchall()
        return [dict(r) for r in rows]

    def get_all_control_ids(self, base_only: bool = False) -> list[str]:
        """
        Return all control IDs in the database.

        Args:
            base_only: If True, exclude enhancements like AC-2(1).

        Returns:
            Sorted list of control ID strings.
        """
        assert self._conn
        if base_only:
            rows = self._conn.execute(
                "SELECT control_id FROM controls WHERE is_enhancement=0 ORDER BY control_id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT control_id FROM controls ORDER BY control_id"
            ).fetchall()
        return [r[0] for r in rows]

    def stats(self) -> dict:
        """Return high-level statistics about the loaded catalog."""
        assert self._conn
        row = self._conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN is_enhancement=0 THEN 1 ELSE 0 END) AS base_controls,
                SUM(CASE WHEN is_enhancement=1 THEN 1 ELSE 0 END) AS enhancements,
                COUNT(DISTINCT family_code)                         AS families
            FROM controls
        """).fetchone()
        return dict(row)


# ---------------------------------------------------------------------------
# Build pipeline — run this to set up the database
# ---------------------------------------------------------------------------

def build_database(force_refresh: bool = False) -> ControlDatabase:
    """
    End-to-end pipeline: download → parse → store.

    Args:
        force_refresh: Re-download and re-parse even if DB exists.

    Returns:
        Opened ControlDatabase ready for queries.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Skip rebuild if DB already exists and we're not forcing refresh
    if DB_PATH.exists() and not force_refresh:
        print(f"[✓] Database already exists at: {DB_PATH}")
        print("    Pass force_refresh=True to rebuild from source.")
        db = ControlDatabase()
        db.connect()
        s = db.stats()
        print(f"    Stats: {s['base_controls']} base controls, "
              f"{s['enhancements']} enhancements, "
              f"{s['families']} families")
        return db

    # Step 1: Download
    json_path = download_nist_json(force_refresh=force_refresh)

    # Step 2: Parse
    records = parse_oscal_catalog(json_path)

    # Step 3: Store
    db = ControlDatabase()
    db.connect()
    db.create_schema()
    db.load_controls(records)

    return db


# ---------------------------------------------------------------------------
# Demo / smoke-test — run `python nist_parser.py` to verify everything works
# ---------------------------------------------------------------------------

def _demo(db: ControlDatabase):
    """
    Quick interactive demo of the ControlDatabase query interface.
    Printed output is what you'd see after `python phase1/nist_parser.py`.
    """
    sep = "─" * 70

    # ── 1. Family summary ───────────────────────────────────────────────────
    print(f"\n{sep}")
    print("NIST SP 800-53 Rev 5 — Control Families")
    print(sep)
    families = db.list_families()
    print(f"  {'Code':<6} {'Family Name':<44} {'Base':>5} {'Enh':>5} {'Total':>6}")
    print(f"  {'─'*6} {'─'*44} {'─'*5} {'─'*5} {'─'*6}")
    for f in families:
        print(f"  {f['family_code']:<6} {f['family_name']:<44} "
              f"{f['base_controls']:>5} {f['enhancements']:>5} {f['total']:>6}")
    s = db.stats()
    print(f"\n  Total: {s['base_controls']} base controls + "
          f"{s['enhancements']} enhancements = {s['total']} entries")

    # ── 2. Single control lookup ────────────────────────────────────────────
    print(f"\n{sep}")
    print("Example: get_control('AC-2')")
    print(sep)
    ctrl = db.get_control("AC-2")
    if ctrl:
        print(f"  Control ID : {ctrl['control_id']}")
        print(f"  Title      : {ctrl['title']}")
        print(f"  Family     : {ctrl['family_code']} — {ctrl['family_name']}")
        print(f"  Parent     : {ctrl['parent_id'] or '(base control)'}")
        print(f"  Enhancement: {'Yes' if ctrl['is_enhancement'] else 'No'}")
        desc_lines = textwrap.wrap(ctrl['description'] or "(no description)", width=66)
        print(f"  Description:")
        for line in desc_lines[:6]:   # truncate for demo
            print(f"    {line}")
        params = json.loads(ctrl["parameters"] or "{}")
        if params:
            print(f"  ODPs ({len(params)} params):")
            for k, v in list(params.items())[:3]:
                print(f"    {k}: {v[:60]}")

    # ── 3. Family drill-down ────────────────────────────────────────────────
    print(f"\n{sep}")
    print("Example: get_family('IA') — Identification and Authentication")
    print(sep)
    ia_controls = db.get_family("IA")
    for c in ia_controls:
        print(f"  {c['control_id']:<12} {c['title']}")

    # ── 4. Full-text search ─────────────────────────────────────────────────
    print(f"\n{sep}")
    print("Example: search_controls('password complexity')")
    print(sep)
    results = db.search_controls("password complexity", limit=5)
    for r in results:
        title_short = r["title"][:55]
        print(f"  [{r['control_id']:<10}] {title_short}")

    print(f"\n{sep}")
    print("Example: search_controls('audit log event monitoring')")
    print(sep)
    results = db.search_controls("audit log event monitoring", limit=5)
    for r in results:
        title_short = r["title"][:55]
        print(f"  [{r['control_id']:<10}] {title_short}")

    # ── 5. Enhancement lookup ───────────────────────────────────────────────
    print(f"\n{sep}")
    print("Example: get_enhancements('AC-2')")
    print(sep)
    enhancements = db.get_enhancements("AC-2")
    for e in enhancements:
        print(f"  {e['control_id']:<14} {e['title']}")

    print(f"\n{'═'*70}")
    print("Phase 1 complete. ControlDatabase is ready for Phase 2+.")
    print(f"Database path: {DB_PATH}")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    # ── Entry point: build the DB and run the demo ──────────────────────────
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 1: Build NIST SP 800-53 control database"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download and re-parse (ignores cached files)"
    )
    parser.add_argument(
        "--lookup",
        metavar="CONTROL_ID",
        help="Look up a single control and print its full details (e.g. AC-2)"
    )
    parser.add_argument(
        "--search",
        metavar="QUERY",
        help="Full-text search the control catalog (e.g. 'password policy')"
    )
    parser.add_argument(
        "--family",
        metavar="CODE",
        help="List all base controls in a family (e.g. IA, AC, AU)"
    )
    args = parser.parse_args()

    db = build_database(force_refresh=args.refresh)

    if args.lookup:
        # ── Single control lookup mode ──────────────────────────────────────
        ctrl = db.get_control(args.lookup)
        if ctrl:
            print(f"\nControl: {ctrl['control_id']} — {ctrl['title']}")
            print(f"Family:  {ctrl['family_code']} ({ctrl['family_name']})")
            print(f"\nDescription:\n{ctrl['description'] or '(none)'}")
            print(f"\nGuidance:\n{ctrl['discussion'] or '(none)'}")
            params = json.loads(ctrl["parameters"] or "{}")
            if params:
                print(f"\nOrganization-Defined Parameters:")
                for k, v in params.items():
                    print(f"  {k}: {v}")
            related = json.loads(ctrl["related_controls"] or "[]")
            if related:
                print(f"\nRelated Controls: {', '.join(related)}")
        else:
            print(f"Control '{args.lookup}' not found in database.")

    elif args.search:
        # ── Search mode ─────────────────────────────────────────────────────
        results = db.search_controls(args.search, limit=10)
        print(f"\nSearch: '{args.search}' → {len(results)} results\n")
        for r in results:
            print(f"  [{r['control_id']:<10}] {r['title']}")
            if r["description"]:
                snippet = r["description"][:120].replace("\n", " ")
                print(f"             {snippet}...")
            print()

    elif args.family:
        # ── Family listing mode ──────────────────────────────────────────────
        controls = db.get_family(args.family)
        if controls:
            family_name = controls[0]["family_name"]
            print(f"\nFamily {args.family.upper()} — {family_name}")
            print(f"{'─'*60}")
            for c in controls:
                print(f"  {c['control_id']:<12} {c['title']}")
            enhancements_total = sum(
                len(db.get_enhancements(c["control_id"])) for c in controls
            )
            print(f"\n  {len(controls)} base controls, {enhancements_total} enhancements")
        else:
            print(f"No controls found for family '{args.family}'.")

    else:
        # ── Default: full demo ───────────────────────────────────────────────
        _demo(db)

    db.close()