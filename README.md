# FaceGuard AI

Face detection, quality assessment, active-liveness challenges and a presentation-attack-detection (PAD) workflow, with a
dashboard, history, reports, dataset management and a model registry.

> **Read this first.** The project ships **no trained anti-spoofing model**. REAL/FAKE verdicts come **only** from a model
> you train on your own data, register, and activate (activation is refused without an identity-disjoint evaluation on at
> least `MIN_EVAL_SAMPLES` test samples). Until then a clean single face is recorded as `UNCERTAIN`, with the reason shown.
> Face detection, a passed blink/head-turn challenge, or good image quality are never treated as proof of a live person.
> See [STATUS.md](STATUS.md) for exactly what was verified and what was not.

## Features
| Area | What works |
|---|---|
| Accounts | Register (first account = administrator), login, silent refresh with rotation and replay detection, logout, change password, profile, e-mail password reset (needs SMTP), 4 roles |
| Verification | Live webcam (detect, 68 landmarks, quality guidance, capture), image upload, video upload, consent gate, results with explanation and the model's score |
| Face detection | YuNet CNN detector (finds tilted, small and dimly lit faces) with automatic fallback to the Haar cascade |
| Liveness model | The active ONNX model scores every image, video (mean over sampled frames) and challenge recording in ONNX Runtime. Conservative decision: an uncertainty band around the model's threshold and a quality gate keep weak evidence `UNCERTAIN` |
| Liveness challenge | Server-evaluated active challenges (blink / head turn, random order, single-use, expiring). Alone it is evidence only; with a model, REAL needs **both** a model REAL score **and** a passed challenge |
| History & reports | Search, filter, sort, paginate, CSV export, delete (owner only); daily/weekly/monthly reports with charts and CSV |
| Datasets | Private labelled image datasets with identity labels, statistics, readiness validation, ZIP export for training |
| Models | Register a trained run from the browser (ONNX + metrics upload, validated with ONNX Runtime) or the CLI, measured PAD metrics, activation guard, evaluation history, delete, training command builder |
| Datasets → training | ZIP export as full images or as **face crops** made by the same detector and crop the API uses at inference time |
| Admin | Users (role, enable/disable), one-time password-reset links (no SMTP needed), audit-log viewer |
| Data collection | Public collection link per dataset (like collect.ekyc.mn, with QR code): participants choose Real/Fake, then a guided phone-camera sequence (face in frame → turn right/left → move closer → hold still → colour flashes) is recorded; 8 single-face frames are added with the label, a pseudonymous person ID and the attack type. No account needed; if a model is active, the participant also sees its score |
| Camera page | **Камераар бичих / Record with camera** in the menu for every signed-in user, and `/start` for visitors without an account: opens the newest collection link (created automatically if none exists). `collect.html` is the same flow as one standalone file (in-browser face detection; host it on GitHub Pages; add `?api=…&token=…` to send recordings to FaceGuard) |
| Admin recovery | `ADMIN_EMAILS=you@example.com` (Render → Environment): that account becomes administrator at its next sign-in |
| Languages | Mongolian and English (МН / EN switch in the header, on the sign-in page and in Settings; remembered per browser). API messages such as result explanations, quality hints, challenge instructions and errors follow the same language |
| Platform | Dark/light theme, role-aware navigation, Docker Compose with Nginx gateway, HTTPS option |

## Architecture
```
Browser ──HTTP(S)──▶ nginx (gateway, only published port)
                       ├─ /api/*  ─▶ backend (FastAPI) ─▶ PostgreSQL        (network "data", internal only)
                       └─ /*      ─▶ frontend (static React build)
backend volume /srv/data: datasets, registered ONNX models         ai/: offline training, evaluation, ONNX export (CLI)
```
```
frontend/        React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query + Recharts (70 tests)
backend/         FastAPI + SQLAlchemy 2 + Alembic + OpenCV (app/, migrations/, scripts/, tests/)
ai/              PyTorch training, evaluation, ONNX export (faceguard_ai/, tests/)
infrastructure/  nginx gateway (HTTP + TLS) and security-header snippets
docker-compose.yml  (+ .dev.yml, .tls.yml)      .env.example      STATUS.md
```

## Requirements
Docker Desktop (Compose v2) **or** Python 3.11+, Node.js 20+, PostgreSQL 16. Windows 11 + PowerShell instructions below.
A webcam needs `http://localhost` or HTTPS (browsers block cameras on plain HTTP elsewhere).

## Fastest start: one command, no Docker (Windows: double-click `start.bat`)
```powershell
cd faceguard-ai
py run.py            # macOS/Linux: python3 run.py   -> opens http://localhost:8000
```
Needs only Python 3.11+. The first run creates `.venv`, installs packages, downloads the landmark model and creates a SQLite
database in `backend/data/`. The API serves the prebuilt web app (`frontend/dist`) itself, so Node.js is not needed.
**Hosting on the internet** (Render, Railway, a VPS) uses the single-container `Dockerfile`: see **[DEPLOY.md](DEPLOY.md)**.

## Quick start: Docker Compose (Windows 11, PowerShell)
```powershell
cd faceguard-ai
Copy-Item .env.example .env

# Generate secrets once (cryptographically random)
function New-Secret([int]$Bytes) { $b = New-Object byte[] $Bytes; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') }) }
(Get-Content .env) `
  -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(New-Secret 16)" `
  -replace '^JWT_SECRET=.*',        "JWT_SECRET=$(New-Secret 32)" | Set-Content .env

docker compose config --quiet          # validates the configuration
docker compose up -d --build           # first build downloads images and the landmark model (internet needed)
docker compose ps                      # wait until db, backend, frontend, nginx are "healthy"
Invoke-RestMethod http://localhost:8080/api/health
```
Open **http://localhost:8080** and register. **The first account becomes the administrator**; later accounts are Viewers
until an administrator changes their role (Administration page). Migrations run automatically when the backend starts.
Stop with `docker compose down` (data is kept in volumes; add `-v` only if you want to delete everything).

> The Docker setup has **not been built or run** in the environment where this was developed (no Docker available). Its
> individual parts were tested separately (see STATUS.md). If `docker compose up` fails, send the output of
> `docker compose logs`.

## Development setup (without building images)
```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db     # PostgreSQL on 127.0.0.1:5432 only
cd backend
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass                    # only if activation is blocked
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python scripts\fetch_models.py          # one-time download of the 54 MB landmark model (SHA-256 verified)
# In .env set ENVIRONMENT=development and APP_BASE_URL/CORS_ORIGINS to http://localhost:5173
alembic upgrade head
uvicorn app.main:app --reload --port 8000        # API docs: http://localhost:8000/api/docs
```
```powershell
cd frontend
npm install
npm run dev                                       # http://localhost:5173 (proxies /api to :8000)
```

## Configuration
Everything is configured through environment variables (`.env`); `.env.example` lists them all. Key ones:

| Variable | Purpose | Default |
|---|---|---|
| `POSTGRES_PASSWORD`, `JWT_SECRET` | **Required.** The app refuses to start with a missing, short (<32) or `CHANGE_ME` secret | none |
| `ENVIRONMENT` | `production` rejects wildcard CORS and warns if docs are on | `production` (compose) |
| `GATEWAY_PORT` / `GATEWAY_TLS_PORT` | The only published ports | `8080` / `443` |
| `APP_BASE_URL`, `CORS_ORIGINS` | Link base for reset e-mails; allowed browser origins | `http://localhost:8080` |
| `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS` | Session lifetimes | 30 / 7 |
| `SMTP_*` | Password-reset e-mail. Without it the feature reports "not available" | empty |
| `REGISTRATION_ENABLED` | Allow self-registration after the first account | `true` |
| `MAX_IMAGE_MB`, `MAX_VIDEO_MB`, `MAX_VIDEO_SECONDS` | Upload limits enforced by the API (Nginx allows 60 MB bodies) | 10 / 50 / 30 |
| `RETENTION_DAYS` | Delete verification results older than N days (0 = keep until owner deletes) | `0` |
| `MIN_EVAL_SAMPLES` | Test-set size a model needs before it can be activated | `200` |
| `RATE_LIMIT_*` | Per-minute limits (0 disables) | see `.env.example` |
| `DOCS_ENABLED` | Swagger UI on the backend (never exposed through the gateway) | `false` |

## Roles
| Role | Can do |
|---|---|
| Viewer | Dashboard, own history/reports, models list (read-only) |
| Operator | + live verification, uploads, challenges |
| Researcher | + datasets, activate/deactivate models |
| Administrator | + users, audit log, all-users **aggregate** report |

Verification records are **private to their owner for every role**, including administrators (no content bypass). An
administrator sees only aggregate counts of other users.

## API
Interactive docs: `http://localhost:8000/api/docs` with the dev setup (46 operations on 39 paths).
Groups: `auth` (login, register, refresh, logout, me, change-password, forgot/reset-password), `users` (list, update, reset-link), `dashboard`,
`face` (capabilities, detect, verify, challenge, challenge/verify), `uploads` (image, video), `verifications`
(list, export, get, delete), `reports` (summary, export), `datasets`, `models` (list, get, register upload, delete, activate, deactivate),
`admin` (audit-logs), `health`. Errors are `{"detail": "...", "errors": [{field, message}]}`.

## Training and registering a model (offline, command line)
You need a labelled dataset **with identity labels** (several images per person, real and attack). Build one on the
Datasets page (readiness checks must pass), download its ZIP, unzip it, then:
```powershell
python -m venv ai\.venv ; .\ai\.venv\Scripts\Activate.ps1
pip install -r ai\requirements.txt            # PyTorch: use the CPU build from https://pytorch.org if you have no GPU
cd ai
python -m faceguard_ai.train --config config.json      # splits by identity, trains, evaluates on a held-out test split
python -m faceguard_ai.export runs\exp1\best.pt runs\exp1\model.onnx
cd ..\backend
python scripts\register_model.py --run-dir ..\ai\runs\exp1 --name smallcnn --version 1.0.0
```
The Models page builds the `config.json` and commands for you. Instead of the CLI you can upload `model.onnx`,
`test_metrics.json` and `split_report.json` with **Register a trained model** on the Models page. Registering never activates
a model. Activation is refused unless the model is trained, its ONNX file is present, and a stored evaluation has
APCER/BPCER/ACER, at least `MIN_EVAL_SAMPLES` test samples, and an identity-disjoint split.

**Face crops (recommended).** Choose *Export face crops* on the dataset page: every image becomes one square face crop
(40 % margin) produced by the same detector and `crop_face()` the API uses at inference. Train on that export and register
with input *Face crops* (`--crop face` on the CLI), so training and serving inputs match exactly.

**How an active model decides** (`backend/app/services/inference.py`): `p = P(bona fide)`, `t` = the threshold stored with
the evaluation. `p ≥ t + LIVENESS_UNCERTAINTY_MARGIN` → REAL, `p ≤ t − margin` → FAKE, otherwise UNCERTAIN. Images failing
the quality checks stay UNCERTAIN (`LIVENESS_REQUIRE_QUALITY`). Videos use the mean over up to 32 sampled single-face frames
and need at least 3. Challenges: model FAKE → FAKE; model REAL **and** challenge passed → REAL; anything else → UNCERTAIN.
The score, threshold and model version are stored with every result and shown on it.

## Testing
```powershell
cd backend ; python -m pytest                                  # unit + integration (temporary SQLite database)
# against PostgreSQL (use a DEDICATED database: the suite drops tables and refuses names without "test")
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec db psql -U faceguard -c "CREATE DATABASE faceguard_test;"
$env:TEST_DATABASE_URL = "postgresql+psycopg://faceguard:<POSTGRES_PASSWORD>@localhost:5432/faceguard_test"
python -m pytest                                               # also runs the Alembic migration test
cd ..\frontend ; npm run typecheck ; npm test ; npm run build
cd ..\ai ; python -m pytest                                    # optional AI tests: skip unless PyTorch/ONNX are installed
```
Tests never download models at test time except the one-time, checksum-verified landmark model. Test images are the
public-domain NASA portrait bundled with scikit-image, or synthetic noise; no private biometric data is used.

## Security summary
Argon2id passwords; short-lived access JWT + single-use rotating refresh tokens with replay detection (a replay revokes the
token family); server-side logout; role checks read from the database on every request; clients can never choose a role;
owner-scoped records; magic-byte upload validation, size/pixel/duration limits, no client file names used as paths;
raw media never stored and temp files overwritten and deleted; CSV formula-injection protection; rate limits in the app
and at Nginx; strict CSP and security headers; internal-only database network; audit log without secrets or biometrics.
Each of these has an automated test, but **no independent penetration test or external security review was done**.

## HTTPS and production
```powershell
# Test certificate (replace with a real one, e.g. from Let's Encrypt, for production):
mkdir certs ; openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=localhost" -keyout certs/privkey.pem -out certs/fullchain.pem
# In .env: GATEWAY_PORT=80, GATEWAY_TLS_PORT=443, APP_BASE_URL=https://your.domain, CORS_ORIGINS=https://your.domain
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
```
Checklist: strong secrets; `ENVIRONMENT=production`, `DOCS_ENABLED=false`; HTTPS with a real certificate; `REGISTRATION_ENABLED=false`
once your users exist; back up the `pgdata` and `appdata` volumes (`docker compose exec db pg_dump -U faceguard faceguard > backup.sql`)
**before** upgrading; schedule `python scripts/purge_retention.py` if you set `RETENTION_DAYS`; do not use results for
high-impact decisions without human review.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Backend exits: "JWT_SECRET ... placeholder" | Run the secret-generation step; values must not contain `CHANGE_ME` |
| `docker compose` says `POSTGRES_PASSWORD` is not set | `.env` must be in the same folder as `docker-compose.yml` |
| Camera permission denied / no camera | Use `http://localhost` or HTTPS; allow the camera in the browser; close other apps using it |
| "Landmark model not found" / "YuNet model not found" warning | `python backend\scripts\fetch_models.py` (needs internet once; downloads both, SHA-256 verified) |
| Results stay Uncertain with a model active | Check the score bar on the result: it is inside the uncertainty band, or the image failed quality checks. `GET /api/health` shows `model_loaded` |
| Login says "Too many attempts" | Rate limit (per IP); wait a minute |
| Password reset says "not available" | Configure the `SMTP_*` variables, or an administrator creates a one-time link: Administration → Users → Reset link |
| Tests refuse to run on PostgreSQL | The database name must contain `test` |

## Known limitations
See [STATUS.md](STATUS.md) for the complete, current list. Most important: no trained model ships with the project (you
must train one on real, identity-labelled data); Label Studio import is not implemented; Docker and real webcam behaviour
were not exercised.

## Translations
- **Web app:** the English text is the key. Wrap new UI text in `t('...')` (from `useT()` in `src/i18n`) and add the Mongolian
  line to `frontend/src/i18n/mn/*.ts`. `npm test` fails if a `t('...')` string has no Mongolian entry or its `{placeholders}` differ.
- **API:** messages are written in English and translated sentence by sentence for `Accept-Language: mn`
  (`backend/app/core/i18n.py`, dictionary and number patterns in `backend/app/locales/mn.py`). Unknown sentences stay English.
  Run the backend tests with `I18N_REPORT_MISSING=missing.txt` to list sentences that still need a translation.
- Stored results keep the explanation in the language that was active when the verification ran.
