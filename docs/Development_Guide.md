# Development Guide

This guide covers local setup, development commands, environment variables, parser changes, and safe Git checks.

## Backend Setup

From the project root:

```powershell
cd SCRmonitor
python -m pip install -r requirements.txt
```

Run the backend with an explicit local data directory:

```powershell
python server.py --host 0.0.0.0 --port 8000 --data-dir .\data
```

The backend initializes SQLite and applies migrations on startup.

## Frontend Setup

Install frontend dependencies:

```powershell
cd SCRmonitor/frontend
npm install
```

Start the Vite dev server:

```powershell
npm run dev
```

Build production frontend assets:

```powershell
npm run build
```

The production build is generated in `SCRmonitor/frontend/dist` and should not be committed.

## Environment Variables

The supported environment variables and their defaults are documented in the
repository [`README.md`](../README.md) (there is no `.env.example`). They cover
the bind host/port, the runtime data and archive directories, optional token
auth, and the test-only mock endpoint toggle.

Never commit real API keys, tokens, passwords, credentials, private
configuration, or local-only secrets. Do not commit `.env`.

## Local Data Directory Setup

For development, use a local runtime data directory that is ignored by Git. The repository includes placeholder `.gitkeep` files under:

```text
SCRmonitor/data/
SCRmonitor/data/uploads/
SCRmonitor/data/outputs/
SCRmonitor/data/logs/
```

Only the placeholders should be committed. Real runtime contents must stay local.

## Common Commands

Backend:

```powershell
cd SCRmonitor
python server.py --host 0.0.0.0 --port 8000 --data-dir .\data
```

Frontend development:

```powershell
cd SCRmonitor/frontend
npm run dev
```

Frontend build:

```powershell
cd SCRmonitor/frontend
npm run build
```

Frontend lint:

```powershell
cd SCRmonitor/frontend
npm run lint
```

## Adding Or Modifying Parser Logic

Parser source lives in `SCRmonitor/parsers/`.

When changing parser behavior:

1. Keep parsing logic in parser modules instead of embedding it in UI code.
2. Keep generated charts, reports, and intermediate files in the runtime output directory.
3. Do not commit uploaded files or real experimental datasets used for manual testing.
4. Update documentation when adding a new supported file format or changing expected input templates.
5. Add or update templates in `SCRmonitor/templates/` only when they are safe examples or required source templates.

## Database And Migration Changes

Schema changes should be represented as new migration files under `SCRmonitor/migrations/`. Do not edit already-applied migrations after they are in shared use. Do not commit local SQLite databases.

See `SCRmonitor/migrations/README.md` for migration-specific rules.

## Safe Git Checks Before Commit

Before staging files, review ignored and staged candidates:

```powershell
git status --ignored
git add -n .
```

The dry-run staging list should not include:

- `.env` or any secrets, tokens, credentials, or private config
- SQLite databases
- runtime uploads, outputs, logs, exports, reports, artifacts, or backups
- `node_modules`
- virtual environments
- Python cache files
- frontend build output
- packaging output or staging folders
- real experimental or business data

If the dry-run output looks safe, then run the real staging command.

