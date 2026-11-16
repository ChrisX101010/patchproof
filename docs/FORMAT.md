# Capsule format v1

An envelope has exactly two fields: `payload` and `sha256`. The digest covers
UTF8 canonical JSON bytes of the payload, not the envelope. The full64-digit
digest is the report identity. This is content addressing, not a signature.

See `examples/buildkit.capsule.json` for a real complete payload. Required fields:

| Field | Meaning |
|---|---|
| schemaVersion | integer1 |
| title, project | report text, maximum200 characters |
| repository, pullRequest | HTTPS source references |
| createdAt | exact UTC `YYYY-MM-DDTHH:MM:SSZ` |
| baseline, candidate | object containing full40/64-digit commit identity |
| environment | os, toolchain, runtime strings |
| groups |1–128 named total/passed/failed/skipped/scope records |
| comparison | name and baseline/candidate total+failed counts |
| limitations |1–32 explicit scope statements |
| evidence |1–1000 unique safe basenames with SHA256 and byte length |

Canonical representation: fixed ASCII object field names, sorted by key,
compact separators, UTF8 strings, no escaping of non-ASCII characters, arrays
preserve order. Counts are nonnegative safe integers, never floats; unknown
fields, duplicate JSON keys, unpaired surrogates, unsafe filenames and
inconsistent counts are rejected. Maximum envelope256KiB; nesting maximum32.

Python and browser encoders share Unicode golden-vector tests. Neither
implementation claims to accept arbitrary RFC8785 JSON; this is a documented
restricted format with integer-only numeric values.

## API

- `GET /api/health`: local/aws mode and schema version.
- `GET /api/example`: bundled real example.
- `GET /api/reports`: at most25 recently indexed public report summaries.
- `GET /api/reports/<digest>`: capsule, checked again against its identity.
- `POST /api/reports`: capability-protected JSON publication.201 new,200
  identical duplicate,401 unauthorized,400 malformed,413 too large,503 storage
  incomplete. The identical publication can be retried after an index failure.
- `GET /r/<digest>`: interface for an existing report.

All capsule content is public after authorized publication. Browser import and
original-file comparison are local operations. The service neither signs claims
nor executes code from a capsule.
