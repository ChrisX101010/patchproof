# Boundaries and limitations

PatchProof checks consistency of provided evidence. A dishonest publisher can
create a self-consistent false report; a hash does not change that. No badge
asserts independent execution, completeness, patch correctness or absence of
vulnerabilities. A stronger attestation system would need a trusted execution
identity and provenance policy; that is outside this demo.

- Strict bounded schema; no uploaded code execution, shell invocation or URL fetch.
- Publisher capability only in a local private file and Lambda environment,
  never in browser assets, report URLs, source control or access logs.
- CLI refuses redirects while sending that capability.
- Same-origin frontend, CSP, text rendering of report values and HTTPS links.
- Private S3 and an app-specific DynamoDB role; conditional capsule writes.
- Corrupt stored bytes are rejected rather than shown as verified.
- Original evidence-file bytes remain in the browser/offline verifier.
- No open public write endpoint. This is a single-owner demo, not multi-tenant SaaS.

AWS account owners and IAM principals who can edit Lambda code/environment or
storage remain trusted administrators. Private local files require appropriate
OS permissions; Windows ACLs are not equivalent to POSIX mode bits. Revoke a
publisher capability by rotating its Lambda environment value and private CLI
file, or remove the demo. Never share `.local/` or a recording of credentials.

This project has had an independent AI code review and automated tests. That
is not an external human audit or a comprehensive security assessment.
