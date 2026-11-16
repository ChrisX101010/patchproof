# Validation

Local verification 2026-11-16.

- 23 Python tests pass; zero skips.
- 11 actual Chrome E2E scenarios pass; desktop/mobile screenshots inspected.
- Real capsule and 16 original evidence fingerprints match.
- Lambda adapter event encoding tested locally.
- Lambda ZIP packaging is reproducible.
- Package entries are uncompressed with fixed Unix metadata so Windows and WSL do not depend on different ZIP compressors.
- Explicit temporary deployment policy and session-bound recording cleanup marker tested locally.
- Independent AI review findings corrected: authenticated redirects, exact timestamp shape, rollback cleanup. Unknown stack creation outcome fails closed for manual inspection.

**AWS deployment and real cloud smoke: PASS on 2026-11-16.** The temporary deployment passed Lambda HTTP, unauthorized-write rejection, private S3 publication/read, DynamoDB listing and idempotent repeat-publication checks. The temporary demo permits variable AWS charges; cleanup is tracked separately.

**Demo recording:** real AWS browser session saved, 114.56 seconds. Saved-video frames inspected and file SHA256 verified.

**Cleanup:** the recorded deployment state is `DELETED`; the owner's cleanup runner confirms `DEMO_ALREADY_DELETED=YES`. The demo endpoint is intentionally temporary. This does not assert that the entire AWS account has no other resources or charges.

Cloud adapters are tested with explicit doubles. These results do not replace real Lambda/S3/DynamoDB smoke testing or guarantee that every defect is excluded.
