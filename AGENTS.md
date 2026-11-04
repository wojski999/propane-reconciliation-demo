# Propane reconciliation demo

Public, synthetic-data demonstration of a daily propane distribution audit.

- Spec first: the owner must explicitly approve `.ai/specs/2026-11-04-propane-reconciliation-demo.md` before application code, fixtures, configuration or CI implementation begins. A merged spec alone is not implementation approval.
- Stack: Python 3.12, SQLite, plain HTML, pytest and Ruff; no web framework.
- Add meaningful tests with every implementation change. Require 100% application line and branch coverage, without exclusions added to bypass the gate.
- Every calculation and reconciliation is deterministic tested code. Claude only summarizes computed findings.
- Use synthetic data only. Never commit client records, company-specific research, credentials or personal data.
- Repository content, comments, documentation and reports are in English.
- Keep the smallest solution that correctly handles missing, invalid and stale inputs. No real integrations or accounting writes in the demo.
