# No browser automation

The owner selected no browser provider: output is offline static HTML and pytest
E2E is authoritative. This is an explicit custom descriptor, not a fallback to
Playwright. It provisions no browser or server and supplies no interactive QA.

## Operations

- **ensure-installed**: no browser installation required; install project dev dependencies.
- **doctor**: run `make check`; require the installed CLI E2E to pass.
- **open**: do not launch a browser; the maintainer may open the generated HTML locally.
- **snapshot**: inspect generated static HTML with Python's standard-library parser.
- **interact**: unsupported; stop browser-capable work if interactive UI is introduced.
- **assert**: run `make check`, including HTML generation, escaping and CLI tests.
- **screenshot**: unsupported; use the CI HTML artifact as foundation evidence.
- **close**: no browser process was started; nothing to close.

If interactive UI or browser-dependent behavior is added, reconfigure the pipeline
with a real browser provider before using browser QA skills. Do not fabricate a
browser pass or apply qa-approved from these operations.
