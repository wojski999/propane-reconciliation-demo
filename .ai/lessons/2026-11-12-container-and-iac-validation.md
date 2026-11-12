# Container and infrastructure validation

Date: 2026-11-12. Source: cloud deployment readiness run.

- Worktree checkouts here can have mode 600 files; `COPY` keeps that mode, so the
  non-root nginx could not read its config and the container exited. Set modes in
  the Dockerfile (`COPY --chmod`, `chmod -R a+rX`) instead of relying on checkout
  umask, and prove it with a real `docker run`, not only `docker build`.
- `bicep build` reports an unknown property only as a warning (BCP037 or BCP089,
  depending on the case) with exit 0. Treat any
  Bicep diagnostic as a failure (`make validate-infra`) and run a negative check
  (deliberately broken property) before trusting a green validator.
- Validators prove schema shape only. Real deployment, HTTPS address and permission
  sufficiency remain "verify after access" items with explicit commands.
