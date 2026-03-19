# CLAUDE.md — AI Assistant Guide for notion-audit-log-s3

## Project Overview

This project is an **AWS serverless pipeline** that captures Notion workspace audit logs via webhook and stores them in Amazon S3 for analysis with Athena and QuickSight.

### Architecture

```
Notion Webhook → API Gateway → Lambda (Python 3.9) → S3 → Athena → QuickSight
                                                     ↓
                                             CloudWatch Logs
```

### Key AWS Resources (defined in `template.yaml`)

| Resource | Details |
|---|---|
| API Gateway | REGIONAL endpoint, `/webhook` POST route |
| Lambda | `notion-webhook-handler`, Python 3.9, 256MB, 30s timeout |
| S3 Bucket | `notion-audit-logs-{AccountId}`, versioning + 7-year lifecycle |

---

## Repository Structure

```
notion-audit-log-s3/
├── lambda/
│   └── handler.py            # Only source file — Lambda function
├── template.yaml             # AWS SAM CloudFormation template
├── pyproject.toml            # Python tooling config (black, bandit)
├── samconfig.toml.example    # SAM deploy config template
├── .pre-commit-config.yaml   # Pre-commit hooks
├── .github/
│   ├── workflows/
│   │   ├── pre-commit.yml    # PR/push code quality checks
│   │   └── security-scan.yml # Security scanning (Trivy, CodeQL, Bandit)
│   └── dependabot.yml        # Automated dependency updates
├── athena-setup.sql          # Athena DB + table creation DDL
├── athena-queries.sql        # Sample analysis queries
├── athena-flat-table.sql     # Flat table schema
├── README.md                 # Project overview (Japanese)
├── SETUP_GUIDE.md            # Step-by-step setup guide (Japanese)
├── GITHUB_SETUP.md           # GitHub repo setup guide (Japanese)
└── SECURITY.md               # Security policy (Japanese)
```

---

## The Only Source File: `lambda/handler.py`

All application logic lives in one file. It has two functions:

### `lambda_handler(event, context)`
- Validates the `x-notion-signature` header against `WEBHOOK_SECRET` env var
- Parses the JSON body
- Calls `flatten_event()` to create an Athena-friendly record
- Writes **two** files to S3:
  - `audit-logs/original/{YYYY}/{MM}/{DD}/{timestamp}.json` — raw backup
  - `audit-logs/flat/{YYYY}/{MM}/{DD}/{timestamp}.json` — single-line for Athena
- Returns HTTP 200/400/401/500 JSON responses

### `flatten_event(audit_data)`
- Flattens nested Notion audit event JSON into a flat dict
- Maps fields to the Athena schema (see `athena-flat-table.sql`)

### Environment Variables

| Variable | Source | Description |
|---|---|---|
| `BUCKET_NAME` | CloudFormation auto-set | S3 bucket for log storage |
| `WEBHOOK_SECRET` | CloudFormation parameter | Notion webhook auth token |

---

## Development Workflow

### Prerequisites

- Python 3.9+
- AWS CLI configured
- AWS SAM CLI installed
- `pre-commit` installed

### Initial Setup

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Copy SAM config and fill in your values
cp samconfig.toml.example samconfig.toml
```

### Deploy

```bash
# Generate a webhook secret
openssl rand -base64 32

# Build the Lambda package
sam build

# First-time deploy (interactive)
sam deploy --guided --parameter-overrides WebhookSecret=<generated-secret>

# Subsequent deploys
sam deploy --parameter-overrides WebhookSecret=<secret>
```

### Tear Down

```bash
sam delete
```

### Athena Setup (after deployment)

```bash
# Create Athena results bucket
aws s3 mb s3://aws-athena-query-results-{AccountId}-{Region}

# Then run in Athena console:
# 1. athena-setup.sql    — creates DB and table
# 2. athena-queries.sql  — sample queries
```

---

## Code Conventions

### Python Style

- **Formatter**: `black` with 88-char line length, Python 3.9 target
- **Type hints**: Use `typing` module (Dict, List, Optional, etc.)
- **Docstrings**: Required for all functions
- **Error handling**: Explicit try/except with specific exception types; always return JSON with `statusCode` and `body`

### S3 Key Naming

```
audit-logs/original/{type}/{YYYY}/{MM}/{DD}/{timestamp_microseconds}.json
audit-logs/flat/{type}/{YYYY}/{MM}/{DD}/{timestamp_microseconds}.json
```

Timestamps use UTC with microsecond precision.

### HTTP Response Format

```python
return {
    "statusCode": 200,
    "body": json.dumps({"message": "...", ...})
}
```

---

## Security Requirements

**Never commit secrets.** The pre-commit hooks and CI enforce this.

### Pre-commit Hooks (run automatically on `git commit`)

- Trailing whitespace / EOF fixers
- YAML + JSON validators
- Large file detector (1000KB limit)
- Private key detector
- AWS credentials detector
- `black` code formatter
- `detect-secrets` secret scanner
- `bandit` Python security linter

### CI Workflows

| Workflow | Trigger | Checks |
|---|---|---|
| `pre-commit.yml` | PRs + pushes to `main` | All pre-commit hooks |
| `security-scan.yml` | PRs, pushes to `main`, weekly | TruffleHog, Trivy (SARIF), CodeQL, Bandit |

### Bandit Configuration

Skip list: `B101` (assert_used is permitted in tests).

---

## Infrastructure Conventions (template.yaml)

- All resources use the SAM `AWS::Serverless::*` transforms
- S3 bucket blocks all public access
- S3 versioning is enabled; lifecycle rule transitions to Glacier after 90 days, expires at 2555 days (7 years)
- `WebhookSecret` parameter uses `NoEcho: true`
- Lambda IAM role is auto-created by SAM with minimal S3 put permissions

---

## What NOT to Do

- Do not add a `requirements.txt` — the Lambda uses only stdlib and `boto3` (built into the Python 3.9 runtime)
- Do not create additional Lambda functions — all logic belongs in `lambda/handler.py`
- Do not store secrets in environment variables in `template.yaml` in plaintext — use `!Ref WebhookSecret` from parameters
- Do not modify S3 key structure without also updating `athena-setup.sql` and `athena-flat-table.sql` (they use `s3://` location paths)
- Do not change the Python runtime version without updating `pyproject.toml` (`target-version`) and all GitHub Actions `python-version` pins

---

## Dependabot

Dependabot is configured to check weekly:
- GitHub Actions versions (`.github/workflows/`)
- Python pip packages in `/lambda`

Auto-created PRs cap at 5 open at a time.

---

## Notes for AI Assistants

1. **All business logic is in one file**: `lambda/handler.py`. Start there.
2. **Infrastructure is all in `template.yaml`**: No CDK, no Terraform.
3. **Documentation is in Japanese**: README.md, SETUP_GUIDE.md, GITHUB_SETUP.md, SECURITY.md are written for Japanese-speaking users. Don't translate unless asked.
4. **No test suite exists**: Testing is integration-based (deploy → trigger → verify S3/CloudWatch). If adding unit tests, place them in a `tests/` directory and configure `bandit` to exclude it (already configured in `pyproject.toml`).
5. **Default deploy region**: `ap-northeast-1` (Tokyo) per `samconfig.toml.example`.
6. **Stack name**: `notion-audit-log-s3`.
