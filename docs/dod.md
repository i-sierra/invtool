# Changelog

## v0.0.0 - Iteration 0. Preparative setup

### Scope

- Minimal operational app: `/` (HTML) + `/health` (JSON).
- Clean folder structure (routes, templates, modular `static/scss`).
- DB prepared (SQLAlchemy 2) and Alembic initialized.
- Tooling: `pytest` (+httpx async), `pytest-cov`, `ruff`, `black`, `isort`, `pre-commit`.
- CI (GitHub Actions) with quality gates (lint, type, tests, coverage ≥80%).
- Batch file with basic tasks.
- Upload limit is parameterized in base configuration.

### Definition of Done

- [x] App runs and `/` and `/health` endpoints work.
- [x] Lint/type/tests are set up and passing in CI.
- [x] Modular SCSS structure + `tasks css` command to compile it.
- [x] Alembic prepared for future use (no migrations yet).

## v0.1.0 - Iteration 1. Advanced setup, error handling and base layout

### Scope

- Config: `secret_key`, sessions, and common utilities.
- Middleware: sessions for flash messages.
- Errors: 404/422/500 with Jinja pages (HTMX-aware).
- Layout: message partial, Bootstrap JS for alerts.
- Support routes (non-prod): `/debug/error` (force 500) and `/demo/flash`.
- VSCode: `.vscode/tasks.json` using `tasks.bat`.
- Tests: 404/500 and flash flow (includes HX‑Redirect).

### Definition of Done

- [x] 404/422/500 pages rendered with Jinja, HTMX-aware.
- [x] Flash messages working with sessions and partial template.
- [x] `/debug/error` and `/demo/flash` routes working (debug only, in prod returns 404).
- [x] Bootstrap JS included; alerts can be dismissed.
- [x] 404/500 tests working and flash working; coverage ≥80%.

## v0.2.0 - Iteration 2. `Part` model + migrations + validation and tests

### Scope

- ORM models: `Part` and `PartType` (SQLAlchemy 2.x).
- Enums: `RohsEnum`, `LifecycleEnum` (with `validate_strings=True`).
- Domain validation: normalization and `ipn` format (`NNNNNN-VV`).
- Repository: basic operations for `Part`.
- Alembic: initial migration (create tables and constraints).
- Unit tests and integration (SQLite temporal file, `instance\app.db` not used).
- Database tasks in `tasks.bat` and `tasks.json`.

### Definition of Done
