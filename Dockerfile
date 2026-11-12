# One image for AWS Lightsail and Azure Container Apps.
# Stage 1 runs the existing CLI on built-in synthetic data; stage 2 serves the
# static result as a non-root user. No secrets, no runtime Python.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS build
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir --disable-pip-version-check . \
    && python -m propane_demo --scenario showcase --output /site \
    && cp /site/report.html /site/index.html \
    && chmod -R a+rX,go-w /site

FROM nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6
LABEL org.opencontainers.image.source="https://github.com/wojski999/propane-reconciliation-demo" \
      org.opencontainers.image.description="Synthetic propane reconciliation demo report"
COPY --chmod=0644 deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site /usr/share/nginx/html
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
