# DexSato Content Control Center — Setup

This patch adds a founder-only Content Control Center without modifying the DexSato decision engine.

## 1. Apply the patch

From the DexSato repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\dexsato_content_control_patch.ps1
```

The script verifies the current Git blob hashes for `app/main.py` and `.env.example` before writing. If those files changed after this patch was prepared, it aborts instead of overwriting newer work. It also creates timestamped backups.

## 2. Configure local environment

Do not put real secrets in `.env.example`. Put them in your local `.env` or your production environment variables.

Generate a session secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add these values to `.env`:

```text
CONTENT_CONTROL_PASSWORD=your-strong-private-password
CONTENT_CONTROL_SESSION_SECRET=your-generated-random-secret
OPENAI_API_KEY=your-openai-api-key
CONTENT_CONTROL_AI_MODEL=gpt-5.6
```

`OPENAI_API_KEY` is optional. Without it, the page uses a deterministic fallback draft.

## 3. Run locally

```powershell
python main.py
```

Open:

```text
http://127.0.0.1:8000/content-control
```

## 4. Production

Set the same environment variables in the deployment environment that serves `app.dexsato.com`. Do not commit real passwords, session secrets, or API keys.

## What this patch changes

Creates:
- `application/content_control_service.py`
- `presentation/content_control_presenter.py`

Updates:
- `app/main.py`
- `.env.example`

Does not modify any market decision, interpretation, signal, observation, technical calculation, or scan engine files.

## V1 flow

DexSato snapshot → private Content Control Center → choose market/content angle → AI or deterministic writing layer → edit → copy → manual post to X.
