# Demo recording — target2 minutes25 seconds

Record the actual AWS deployment after `tools/smoke.py` passes. Keep local
development footage clearly labelled local; it cannot replace the required
working AWS build. No licensed music, borrowed logos, credentials or fake
console screens. Use your own voice; trim pauses before upload. The public
video must be shorter than3 minutes and use an accepted video platform.

## 0:00–0:20 — Open the real report

Screen: AWS report permalink, the before/after chart and runtime mode visible.

“A green check does not tell you what was tested. While preparing a BuildKit
patch, I had sixteen evidence files and a result worth explaining: seven
missing-base failures before the fix, zero after, in twenty image cases each.
PatchProof makes that evidence portable.”

## 0:20–0:45 — Show both result and boundary

Screen: overview and explicit limitations. Do not open a page containing secrets.

“The report keeps the commits, environment and scope together. These are
forty-six cache tests, normally and with the race detector. It also says
that the full integration suite and an existing-state upgrade were not tested.”

## 0:45–1:10 — Verify original evidence

Screen: evidence manifest. Select the original known evidence files using a
prepared directory containing no unrelated files. Show the matches summary.

“Every file has a fingerprint. This comparison runs in the browser; the
original logs are not uploaded. Somebody reviewing my work can check their
copy instead of trusting a screenshot.”

## 1:10–1:35 — Tamper and verify

Screen: Integrity lab, Change a number, then Recheck original.

“If I change one reported number, the recorded digest no longer matches.
The demonstration changes a copy. Hashes do not prove that tests really
happened, and the app does not pretend they do.”

## 1:35–1:55 — Take it away

Screen: Download proof, then a clean terminal with the offline verifier output.

“The capsule is ordinary JSON. Download it and verify it with Python, without
an account, this website or an AI service. The format is documented.”

## 1:55–2:25 — Explain AWS and close

Screen: Architecture tab; live URL and AWS runtime mode. Optionally show only
the sanitized cloud smoke receipt, never `.local/` or publisher token contents.

“One Lambda serves the interface and API. Private S3 stores immutable
capsules; DynamoDB indexes reports. Repeating a publication is safe, and a
retry can repair an interrupted index write. No VM or deployment pipeline.
My goal is simple: make a software fix easier to review, and keep its
evidence useful after the weekend ends.”

## Submission checklist

- [x] Real AWS smoke test PASS and report accessible anonymously during recording.
- [x] Owner approved temporary metered demonstration; recorded resources subsequently deleted.
- [ ] Source repository published; README matches actual tested/deployed state.
- [ ] Video actually recorded, public, accepted host, duration<3 minutes.
- [ ] Article placeholders replaced; no untested claims added.
- [ ] Builder Center profile and eligibility checked; join the exact challenge.
- [ ] Project submission includes the video in its demo field before deadline.
- [ ] Verify final published project URL and contest association.

## Actual recording

The saved AWS demonstration is `artifacts/patchproof-aws-demo.webm` and lasts
114.56 seconds. It uses readable captions and shows the real browser interactions.
Local rehearsal footage is a separate file and must not be submitted as AWS proof.

Suggested public video title:

**PatchProof — portable patch evidence on AWS Lambda, S3 and DynamoDB**

Suggested description:

I built PatchProof to make a software contribution easier to review. A portable
JSON capsule keeps the before/after result, scope, limitations and original-file
fingerprints together. The demo uses my real BuildKit contribution: seven
missing-base failures in twenty cases before the patch, zero in twenty afterward.

This is the actual temporary AWS deployment: Lambda Function URL serves the UI
and API, private S3 stores immutable capsules, and DynamoDB indexes reports.
The deployment passed real service smoke checks and was deleted after recording
to limit cost. No always-on server or deployment pipeline.

Fingerprints check byte consistency; they do not prove independent execution.
Built by Hristos Nenkov with AI assistance.
