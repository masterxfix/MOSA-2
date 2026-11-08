"""One controlled, read-only GET of the pinned official NEL Q2 PDF.
Run explicitly in isolated CI. No database, archive, credentials, or writer.
"""
from datetime import datetime, timezone
import hashlib
import json
from urllib.request import Request, urlopen

from scripts.fundamentals import nel_q2

EXPECTED_SOURCE_SHA256 = "60336ebdbcba904234ea9c40a759eb22baf9892fab571651b78e3c319f89a116"
EXPECTED = {
    "revenue": "153407",
    "ebitda": "-155337",
    "ifrs_operating_profit": "-205220",
    "profit_after_tax": "-188571",
    "operating_cashflow": "1673",
}

def main():
    request = Request(nel_q2.URL, headers={"Accept": "application/pdf", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=30) as response:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(8 * 1024 * 1024 + 1)
    digest = hashlib.sha256(raw).hexdigest()
    if not (status == 200 and content_type.lower().startswith("application/pdf")
            and 0 < len(raw) <= 8 * 1024 * 1024 and digest == EXPECTED_SOURCE_SHA256):
        raise ValueError("NEL_SOURCE_BINDING_OR_HASH")
    metadata = dict(url=nel_q2.URL, observed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
                    http_status=status, content_type=content_type, bytes=len(raw), sha256=digest)
    identity = dict(isin=nel_q2.ISIN, name="NEL ASA")
    try:
        plan = nel_q2.parse(raw, metadata, identity)
    except ValueError:
        # Fail-safe public-source diagnostics, bounded and without source-byte archival.
        pages = nel_q2.read_pdf(raw, max_bytes=16 * 1024 * 1024, max_pages=40,
                                max_characters=1000000)
        income = nel_q2._tables(pages, nel_q2.TABLE_PATTERNS["income"],
                                "Consolidated statement of comprehensive income")
        print("NEL_DIAG income_rows=" + str(len(income)), flush=True)
        for entry in income[:40]:
            print("NEL_DIAG income page=" + str(entry["page"]) +
                  " row=" + entry["row"][:140] + " value=" + str(entry["value"]), flush=True)
        raise
    actual = {row["metric_key"]: row["value_decimal"] for row in plan["observations"]}
    if actual != EXPECTED:
        raise ValueError("NEL_REAL_PDF_VALUES")
    evidence, archive_metadata = nel_q2.evidence(plan, metadata, identity)
    if len(json.loads(evidence)["facts"]) != 5 or archive_metadata["sha256"] != hashlib.sha256(evidence).hexdigest():
        raise ValueError("NEL_REAL_PDF_EVIDENCE")
    print("NEL_REAL_PDF_READONLY_OK source_sha256=" + digest + " facts=5 " +
          "period=fq:2026-04-01..2026-06-30")
    # The original response is never archived or committed.

if __name__ == "__main__":
    main()
