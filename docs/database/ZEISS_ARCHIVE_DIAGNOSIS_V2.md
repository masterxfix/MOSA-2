# Zeiss archive diagnosis transport repair

Starting commit: 1216bb99097999e1d4fbc8e106ec3754a812f84d.
Scope: diagnosis only; no adapter correction, database connection, provider GET,
deployment or archive mutation. One completion commit and one manual run.

The previous reader returned the complete body as Base64 JSON through
`collector_db_locality.remote_call`, whose unchanged MAX_OUTPUT is 65536 bytes.
49152 raw bytes already encode to 65536 bytes before the JSON envelope. The
focused test reproduces SSH_OUTPUT_LIMIT through that actual transport function.

The replacement sends only reviewed Python code over the existing pinned SSH
connection. The unchanged PNE helpers and Zeiss adapter are loaded as in-memory
modules under the existing isolated Python 3.11 interpreter. Original bytes stay
in that remote process. No module files are uploaded or installed.

The original marker, metadata, owner/mode/no-follow protections, 8 MiB file cap,
exact expected SHA-256, commit, URL, size and acquisition time are checked before
the adapter runs. Both original files are reread and compared. Only structural
diagnosis and fixed error codes return, capped at 16384 bytes below the unchanged
transport limit. Raw exception text, HTML, values and private paths are excluded.
The result also reports whether the actual body's former Base64 envelope would
exceed the transport cap; no second transfer is attempted.

Errors identify GUARDS, CONFIGURATION, SSH_CONNECT, SSH_REMOTE_DIAGNOSIS,
ARCHIVE_PATHS, ARCHIVE_MARKER, ARCHIVE_BYTES, ARCHIVE_METADATA,
ARCHIVE_READBACK or ADAPTER, plus an allowlisted safe code.

Workflow: fundamentals-zeiss-diagnose-v2.yml; manual main revision,
run number/attempt 1, exact SHA and separate authorization
MOSA2-ZEISS-ARCHIVE-DIAGNOSE-V2-20261101:<commit>.
No DB secret is supplied. No automatic trigger or retry.

Five focused offline tests cover the real transport overflow, a synthetic archive
over 512 KiB through the assembled remote code with a read-only fake filesystem,
unchanged protection guards, first adapter error and structural-only output.
The real archive diagnosis remains the single live run's result; synthetic
success alone does not establish its actual adapter failure.
