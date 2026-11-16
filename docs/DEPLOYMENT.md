# Deploy without authorizing paid charges

## Explicitly authorized temporary metered demo

The owner has separately approved a small variable charge for a temporary
demonstration. This exception does not authorize permanent hosting or a claim
of zero cost. Use this one owner-run WSL workflow rather than changing guards:

```sh
python tools/temporary_demo.py --start --minutes 60
```

It verifies the exact locally tested package, deploys with a recorded
TEMPORARY_METERED_DEMO policy, exercises real AWS HTTP/S3/DynamoDB, then waits
for recording. Keep the WSL terminal open. The project's verified recording
completion marker triggers cleanup automatically. For a manually saved video,
type `DONE`. At most60 minutes after cloud smoke readiness, cleanup starts
while the script remains running. Closing/killing WSL or switching off the
machine can prevent that cleanup: this is not an AWS-side spending cap.

The wrapper invokes only the existing account/stack-verified cleanup tool.
Check DEMO_CLEANUP=PASS and the saved deletion state. If creation or cleanup
is incomplete, inspect the recorded AWS stack immediately; never infer that
resources were removed. The resulting public source/video can remain, but
the deleted AWS endpoint must not be presented as still live.

The following sections document the separate, default Free-plan workflow.

## 1. Verify your account

Install current AWS CLI2 and sign in with `aws login --remote` or your normal
IAM Identity Center profile. Do not send credentials or login codes to anyone.
An optional per-user signed installer is `tools/install_aws_cli.py --install`
on Linux/amd64. It checks AWS's signing-key fingerprint and package signature,
uses `~/.local/`, does not need sudo, and never upgrades an existing install.

```sh
export PATH="$HOME/.local/bin:$PATH"
aws login --remote
python tools/deploy.py
```

The gate uses STS identity and the official GetAccountPlanState API. It requires
FREE, ACTIVE, positive remaining USD credits, an unexpired plan, and matching
account identities. Missing CLI permissions, PAID or unknown plans block writes.
It checks the plan again immediately before creating resources. These are
account-plan checks, not an assertion that paid-account Free Tier allowances
can never be exceeded. No budget alarm is treated as a spending cap.

Sources: [AWS plan behavior](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html),
[plan API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_freetier_GetAccountPlanState.html),
[browser sign-in](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

## 2. Create the demo explicitly

```sh
python tools/deploy.py --deploy --accept-free-plan --region us-east-1
```

This creates a private artifact bucket and the CloudFormation stack
`patchproof-demo`: Lambda128MB/15s, a Function URL, a private encrypted S3
bucket, an on-demand DynamoDB table, an IAM execution role and a log group
with3-day retention. No VM, VPC, NAT, domain, provisioned concurrency or pipeline.
S3 report access is restricted to `capsules/*`; DynamoDB actions to its table.
Both function URL invocation permissions are included, as required for new URLs.

Package manifest is `dist/package-manifest.json`. A unique publisher capability
is saved in `.local/aws-publisher-token` and passed through a NoEcho stack
parameter. It is not a browser asset, output, URL or log. Deployment metadata
is saved in `.local/aws-state.json`. Never publish that directory.

If deployment fails, inspect the saved receipt and the stack events; do not
delete the receipt or rerun blindly. The tool refuses a second deployment when
that receipt exists. Use the inspected cleanup path before retrying.

## 3. Verify the real cloud

```sh
python tools/smoke.py
```

This checks the account plan again, actual Lambda HTTP, denied anonymous
publication, authenticated S3 capsule write/read, DynamoDB discovery and repeat
publication. It uses the genuine example and saves `.local/cloud-smoke.json`.
Only after PASS is the report URL suitable for a working AWS demo. Unit
storage doubles and local SQLite tests do not prove cloud readiness.

For a non-default profile use `--profile NAME` when deploying; that profile is
recorded for smoke/cleanup. Required IAM privileges are the normal deployment
rights for the listed resources, `iam:PassRole` and `freetier:GetAccountPlanState`;
the app's runtime role is much narrower. Never add administrator access merely
to bypass an unexplained permission error.

## 4. Remove this demo when wanted

```sh
python tools/cleanup.py                 # inspect only
python tools/cleanup.py --delete-demo   # permanently delete demo and capsules
```

Cleanup verifies the account, recorded stack and Project tag. It empties only
that stack's report bucket, deletes its stack and unique artifact bucket, and
retains a deletion receipt. It never prunes builders, unrelated buckets or other
projects. Confirm the stack is gone in AWS; a failed cleanup is not a deletion
receipt. The short-lived Free account remains your account to manage.

Cloud deployment is not performed merely by installing the CLI, running local
tests, packaging the ZIP or opening the website locally.
