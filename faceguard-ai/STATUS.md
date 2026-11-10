# STATUS

## Update: public data-collection links
- Datasets page → **Collection link** card: turn on, copy link / QR code, rotate, turn off. `/collect/<token>` works without an account.
- Flow verified in headless Chromium with a fake phone camera (iPhone 13 viewport): label → instructions + consent →
  camera steps with live guidance → colour flashes → upload → result; 8 labelled frames added; no console errors.
- Backend 323 passed / 1 skipped, frontend 88 passed. Head-turn detection was exercised only with timeouts (a still
  test image cannot turn); check it on a real phone.

---

## Update: Mongolian / English interface
- Every page, dialog, toast, chart label and validation message of the web app is available in Mongolian and English
  (switch in the header, sign-in page and Settings; remembered in the browser; the first visit follows the browser language).
- The API answers in the same language (`Accept-Language`): result explanations, quality checks and guidance, challenge
  instructions, dataset/model readiness messages and error messages. Unknown sentences fall back to English.
- Dates use the numeric Mongolian form (2026.11.10 21:34), independent of the browser's locale data.
- Verified: frontend 86 tests (including a check that every `t()` string has a Mongolian entry), backend 314 passed / 1 skipped
  (PostgreSQL-only test), real-browser walkthrough of all ten pages in Mongolian with no remaining English UI text except
  product names, file names and commands; English flow re-run unchanged; phone width 390 px without sideways scrolling.
- The translations were written for this project and have not been reviewed by a professional translator.

---

## Update: liveness inference, YuNet detector, model upload, admin reset links
Executed in this session (Linux, Python 3.13, Node 22, PostgreSQL 16, onnxruntime 1.31, OpenCV 4.14):

| Check | Result |
|---|---|
| Backend `pytest`, PostgreSQL 16 | **309 passed** (includes the Alembic upgrade / drift-check / downgrade test with new migration `0003`) |
| Backend `pytest`, SQLite | **308 passed, 1 skipped** (the PostgreSQL-only migration test) |
| Frontend `npm run typecheck` / `npm test` / `npm run build` | **clean / 80 passed (18 files) / passed** |
| Real browser (headless Chromium, `frontend/dist` served by the API) | register → upload a model on the Models page → activate → upload an image → **REAL with score bar** → admin reset link → reset page. No console errors. Phone width (390 px): no horizontal scrolling |
| `run.py` on a fresh copy | creates `.venv`, installs the new `onnxruntime` dependency, downloads LBF + YuNet (SHA-256 verified), migrates, serves |

What changed:
- **Model inference is wired in** (`backend/app/services/inference.py`). The active ONNX model scores images, videos (mean over
  up to 32 sampled frames, at least 3) and challenge recordings. `p ≥ threshold + margin` → REAL, `p ≤ threshold − margin` → FAKE,
  otherwise UNCERTAIN; images failing quality checks stay UNCERTAIN. Challenge: REAL needs model REAL **and** a passed challenge.
  Score, threshold and model are stored on each result and shown as a score bar. Preprocessing is asserted identical to
  `ai/faceguard_ai/data.preprocess` by a test. A model whose file disappears or is corrupted after activation is reported, never
  silently used. `/api/health` `model_loaded` is now true only when the active model really loads.
- **YuNet face detector** (OpenCV Zoo, MIT) with automatic Haar fallback (`FACE_DETECTOR=auto|yunet|haar`). Finds a 25°-tilted
  face Haar misses (tested). Boxes are converted to Haar geometry so landmarks and quality thresholds keep working.
- **Register a model from the browser** (ONNX + `test_metrics.json` + `split_report.json`; validated with ONNX Runtime; never
  activated) and **delete** inactive models. CLI and form share one code path. Models record whether they expect face crops.
- **Dataset export as face crops**, made by the same detector and crop function as inference, so train and serve inputs match.
- **Administrator password-reset links** (one-time, expiring, optional sign-out everywhere; no SMTP needed; token never logged).
- Fixed: the app header was 16 px wider than a 390 px phone screen on every page; the Admin table pushed the page sideways.

Still true: **no trained model ships with the project**. The inference path was tested with small hand-built ONNX graphs whose
outputs are known exactly, not with a real anti-spoofing network. Until you train and evaluate one on real, identity-labelled
data, results stay UNCERTAIN.

---

## Earlier record

Updated after a session that **executed** everything below on a machine with network access (Linux, Python 3.12, Node 22,
PostgreSQL 16, PyTorch 2.14 CPU via conda-forge, nginx 1.31). Earlier versions of this file said the code had never been run;
that is no longer true for the items marked *Executed*. Items marked *Not executed* still have not been.

## Verification results
| Check | Result | Notes |
|---|---|---|
| Backend `pytest`, PostgreSQL 16 | **Executed: 250 passed** | includes the Alembic upgrade / drift-check / downgrade test |
| Backend `pytest`, SQLite | **Executed: 249 passed, 1 skipped** | the skip is the PostgreSQL-only migration test |
| Frontend `npm run typecheck` | **Executed: clean** | |
| Frontend `npm test` (Vitest + jsdom) | **Executed: 75 passed** | 17 files |
| Frontend `npm run build` | **Executed: passed** | route-level code splitting |
| AI `pytest` with PyTorch 2.14 (CPU), ONNX, onnxruntime | **Executed: 5 passed** | real training loop on a *synthetic* smoke dataset, ONNX export, ONNX-vs-PyTorch parity |
| AI `pytest` without ML packages | **Executed: 2 skipped** | optional tests skip, they do not error |
| API served through real nginx instances (frontend + gateway + TLS) in front of the real API on PostgreSQL | **Executed** | headers, SPA fallback, caching, docs blocked, refresh-replay detection, forged `X-Forwarded-For` ignored, login rate limit, 413 on oversize body, HTTP to HTTPS redirect, HSTS, TLS 1.3 |
| `nginx -t` on all three project configs | **Executed: ok** | |
| CLI register of a really-trained smoke model into PostgreSQL with onnxruntime validation | **Executed** | activation correctly refused (12 test samples < 200) |
| `docker compose config` / `docker compose build` / `docker compose up` | **Not executed** | no Docker in the build environment. Compose files are covered by static tests only (12) |
| Frontend in a real browser (layout, theme, drag-and-drop, charts) | **Partly executed** | key pages in headless Chromium via run.py (see below); not every page or the light theme |
| Webcam capture, camera permission prompt, MediaRecorder challenge recording | **Not executed** | needs a camera and browser. Hooks are tested with mocks |
| Anything on Windows | **Not executed** | PowerShell commands are written for Windows 11 but were run on Linux equivalents |
| Single-process mode `run.py` (SQLite, API serves the web app), fresh `.venv` | **Executed** | real Chromium: register, dashboard, image upload, live webcam (fake camera device) with face box and landmarks, history; no console errors |
| Single-container `docker-entrypoint.sh` in the `/srv` layout of the root `Dockerfile` | **Executed** | migrations, privilege drop to uid 10001, SQLite on the data volume, SPA + API |
| Root `Dockerfile` `docker build` | **Not executed** | Docker Hub unreachable from the build environment |

## Feature status
| Feature | Status |
|---|---|
| Authentication (register, login, refresh rotation + replay detection, logout, change password, profile, e-mail reset) | Implemented. E-mail reset needs SMTP: **never exercised against a real mail server** |
| Roles and owner-scoped records | Implemented, tested (isolation, no admin bypass) |
| Face detection, landmarks, quality checks | Implemented (OpenCV Haar + LBF-68). Frontal faces only; thresholds tuned on one public-domain image |
| Live webcam, image upload, video upload | Implemented; browser behaviour not exercised |
| Active liveness challenge | Implemented (server-evaluated landmark state machine). Accuracy **not evaluated** on real recordings; a pass is evidence only |
| Verification history, CSV export, delete | Implemented, tested |
| Reports (day/week/month), CSV export | Implemented, tested |
| Datasets (private, identity labels, validation, ZIP export) | Implemented, tested. Stored on the filesystem volume; the unused `datasets`/`dataset_samples` DB tables remain from the original schema |
| Model registry, activation guard, evaluation history | Implemented, tested |
| Registering a trained run | CLI (`backend/scripts/register_model.py`) and upload form on the Models page |
| Training pipeline (identity-disjoint split, metrics, checkpoints, ONNX) | Implemented and executed on synthetic data. **Never trained on real data** |
| Training from the UI / job tracking / progress | **Not implemented.** The page generates the command and says so |
| Model inference inside verification (ONNX Runtime in the API) | **Implemented** (see update above). Tested with synthetic ONNX graphs; never with a real trained PAD model |
| Admin: users, audit log, password-reset links | Implemented, tested |
| Retention purge | Implemented, opt-in (`RETENTION_DAYS`, default off), tested |
| Light/dark theme, role-aware navigation, error boundary | Implemented |
| Label Studio import/sync | **Not implemented.** `LABEL_STUDIO_*` variables are reserved and read by nothing |
| Docker Compose (db, backend, frontend, nginx), internal networks, HTTPS override | Written and statically tested; **not run** |

## AI model
**No trained anti-spoofing model exists.** The only model ever trained here is a smoke-test network on synthetic noise images;
its perfect scores mean nothing and the registry correctly refuses to activate it. Until a model is trained on a real,
identity-labelled dataset, evaluated on an identity-disjoint test split with at least `MIN_EVAL_SAMPLES` samples, **and**
wired into the verification pipeline, results are `UNCERTAIN`, `NO_FACE`, `MULTIPLE_FACES` or `ERROR`, never `REAL`/`FAKE`.

## Bugs found by running the code, and fixed
1. Token refresh returned HTTP 500 on SQLite: five bulk `UPDATE/DELETE` statements compared tz-aware and naive datetimes in Python.
2. A table-inventory test was stale after migration `0002` (refresh and reset tokens).
3. ONNX export failed on current PyTorch (undeclared `onnxscript` dependency) and produced a model whose weights sat in a separate
   `.data` file, so copying the `.onnx` alone would give a model that cannot load. Export is now one self-contained file, tested.
4. The frontend ignored refresh tokens, so every session would have ended when the access token expired. Silent single-flight refresh added.
5. The gateway put token refresh in the strict login rate limit (routine traffic from users behind one IP would be blocked). Moved.
6. `ENVIRONMENT` was defined but read by nothing. Production now rejects wildcard CORS and warns on public API docs.
7. The compose file published PostgreSQL and the backend on host ports. Now only the gateway publishes; the database network is internal.
8. Nothing ever expired old verification results. Opt-in retention purge added.
9. Nothing could register a trained model, so the Models page could never show one. Register CLI added.
10. The forgot-password page told users to "ask an administrator", who cannot reset passwords. Text corrected.
11. Optional AI tests errored during collection when ML packages were absent. They skip now.
12. 9 placeholder pages replaced with working pages; the placeholder component was deleted.
13. API-versus-TypeScript contract is now enforced by tests (parses the real TS interfaces). Not covered: the challenge-result shape.

14. Migrations used PostgreSQL's `now()` as a column default, so creating any user failed on a migrated SQLite database
    (tests had only used `create_all`). Now `sa.func.now()` (identical on PostgreSQL; regression test added).

## Remaining issues and blockers
- **Blocker for real anti-spoofing:** a real, identity-labelled dataset (many people, real captures plus print/screen/replay attacks)
  and a model trained and evaluated on it. The inference integration now exists; the data and model do not.
- Docker build/run and browser/webcam behaviour must be confirmed on your machine (commands are in README.md).
- Refresh and access tokens live in `sessionStorage` (readable by any script on the page). A strict CSP is set at the gateway, but an
  `HttpOnly` cookie design would be stronger.
- No independent security review or penetration test was done. Rate limiting in the app is in-memory (single process).
- YuNet is now the default detector. LBF landmarks (used by the blink/turn challenge) are still a frontal-face model.
- The uncertainty margin and quality gate are conservative defaults, not tuned on real data. Calibrate them on your own validation set.
- Dataset ZIP import and Label Studio export import are not implemented (images are added through the UI).
