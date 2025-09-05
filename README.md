# Inventory Manager (FastAPI + SQLAlchemy + HTMX)

## Quickstart

### Windows (CMD) – sin Make
```bat
python -m venv .venv
call .venv\Scripts\activate
copy .env.example .env
mkdir instance app\static\css
tasks init
tasks run
```

To compile SCSS to CSS, you need to have [Dart Sass](https://sass-lang.com/install) installed and available in your PATH (for example, by installing [Chocolatey](https://chocolatey.org/install) and running `choco install sass`). Then, in another terminal, run:
```bat
tasks css
```
