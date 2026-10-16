# Loan Eligibility Prediction System — Epic 1 Integration, Testing & Deployment

[![Django CI & Test Pipeline](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![Python 3.12 | 3.14](https://img.shields.io/badge/Python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Django 6.1.2](https://img.shields.io/badge/Django-6.1.2-green.svg)](https://www.djangoproject.com/)
[![Render Deploy](https://img.shields.io/badge/Deploy-Render-46E3B7.svg)](https://render.com/)

## 1. Project Overview
The **Loan Eligibility Prediction System** is a secure, production-grade Django REST API platform engineered to evaluate customer creditworthiness and estimate loan eligibility. It integrates user authentication, loan application lifecycle management, machine learning inference with calibrated underwriting heuristics, and Django administration audit controls.

---

## 2. Technology Stack
* **Language & Framework:** Python 3.12+ / 3.14+, Django 6.1.2
* **API Framework:** Django REST Framework (DRF) 3.18.3
* **Production WSGI Server:** Gunicorn 21.2+
* **Static Asset Management:** WhiteNoise 6.6+ with compressed manifest storage
* **Databases:** SQLite (local development and testing) / PostgreSQL (Render production via `dj-database-url` and `psycopg2`)
* **Machine Learning:** Scikit-Learn / Joblib pipeline compatibility with a built-in calibrated logistic underwriting scoring engine fallback
* **Containerization:** Docker (multi-stage non-root container) & Docker Compose
* **CI/CD:** GitHub Actions
* **Hosting Platform:** Render

---

## 3. Architecture & Module Responsibilities

| Module | Core Files | Responsibility |
| :--- | :--- | :--- |
| **Authentication & Profile** | `loanapp/views.py`, `loanapp/serializers.py` | Registration, credential validation, token & session authentication, logout token revocation, and user profile. |
| **Loan Application Lifecycle** | `loanapp/models.py`, `loanapp/views.py`, `loanapp/serializers.py` | Strict applicant data validation (age 18–100, positive income & loan amount, CIBIL 300–900). Guaranteed user binding to `request.user` to eliminate identity spoofing. |
| **ML Prediction Service** | `loanapp/ml_service.py` | External joblib artifact loader (`loan_model.joblib`) with automatic fallback to a calibrated logistic underwriting model (CIBIL 45%, DTI 35%, Income 15%, Age 5%). Outputs probability, eligibility status, risk factors, and disclaimers. |
| **Django Administration** | `loanapp/admin.py` | Formatted financial representations, currency masks, read-only prediction metrics, search, and audit filters. |
| **System Health Monitoring** | `loanapp/views.py` (`/healthz/`, `/api/health/`) | Unauthenticated readiness probes verifying live database connectivity and ML status for Docker and Render. |

---

## 4. API Endpoints

### System Probes
* `GET /healthz/` or `GET /api/health/` — System readiness and database connectivity probe (Public).

### Authentication
* `POST /api/register/` — Register a new account with email uniqueness and password complexity (Public).
* `POST /api/login/` — Authenticate using username or email and obtain auth token (Public).
* `POST /api/logout/` — Flush session and revoke auth token (Requires Authentication).
* `GET /api/me/` — Retrieve profile of current logged-in user (Requires Authentication).

### Loan Applications & Inference
* `POST /api/loans/` — Submit application, perform ML evaluation, and persist record (Requires Authentication).
* `GET /api/loans/list/` — List loans with strict data isolation: regular users only see their own; staff/admins can view all (Requires Authentication).
* `GET /api/loans/<id>/` — View single loan application with cross-user access prevention (Requires Authentication).
* `POST /api/predict/` — Interactive eligibility evaluation without database persistence (Requires Authentication).

---

## 5. Prerequisites
* Python 3.12 or higher installed
* Git installed
* (Optional) Docker installed for container testing

---

## 6. Local Setup & Execution

### 1. Clone & Set Up Virtual Environment
```powershell
git clone <YOUR_REPOSITORY_URL>
cd LoanEligibility

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```

### 3. Apply Database Migrations
```powershell
python manage.py migrate
```

### 4. Create Superuser (Admin Access)
```powershell
python manage.py createsuperuser
```

### 5. Collect Static Files
```powershell
python manage.py collectstatic --noinput
```

### 6. Run Automated Tests
```powershell
python manage.py test
```

### 7. Run Development Server
```powershell
python manage.py runserver
```

---

## 7. Automated Test Suite

The test suite covers unit, integration, negative edge cases, authorization isolation, and system health checks.

* **Command:** `python manage.py test`
* **Total Tests:** 34
* **Passed:** 34
* **Failed:** 0
* **Execution Time:** < 1.5 seconds

### Test Suites Included:
1. `AuthenticationTests` (9 tests): Registration, duplicate username/email, login via username/email, invalid password, nonexistent user, token revocation.
2. `LoanValidationAndCreationTests` (8 tests): Valid submission, anti-spoofing enforcement, boundary ages (18, 100), invalid ages, non-positive income/loan amounts, CIBIL range checks.
3. `AuthorizationAndDataIsolationTests` (4 tests): Anonymous request rejection, borrower data isolation, cross-user detail view blocking (403 Forbidden), staff administrative access.
4. `MLPredictionModuleTests` (3 tests): Prime credit evaluation, subprime credit rejection, out-of-range input handling.
5. `EndToEndWorkflowTests` (1 test): Complete end-to-end borrower journey from registration to evaluation and logout.
6. `HealthCheckTests` (3 tests): Public `/api/health/`, root `/healthz/`, and simulated database connection failure.
7. `NegativeAndEdgeCaseIntegrationTests` (6 tests): Unsupported HTTP methods, non-numeric malformed JSON, unauthenticated prediction requests.

---

## 8. Docker Build & Run

### Build Docker Image
```bash
docker build -t loan-eligibility-api .
```

### Run Docker Container
```bash
docker run -p 8000:8000 \
  -e DJANGO_SECRET_KEY="docker-run-test-secret-key-1234567890-secure" \
  -e DJANGO_DEBUG="True" \
  -e DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1" \
  loan-eligibility-api
```

### Run with Docker Compose
```bash
docker-compose up --build
```

---

## 9. GitHub Branching Workflow

Follow this branch structure for development and integration:
* **`main`**: Production-ready, stable releases.
* **`develop`**: Integration branch for combining tested features.
* **`feature/developer-5`**: Integration, testing, production artifacts, and deployment branch.

### Creating and Switching Branches
```bash
# Check current status
git status

# Switch to feature branch
git checkout -b feature/developer-5

# Stage and commit reviewed changes
git add .
git commit -m "feat(integration): integrate Epic 1 modules, tests, Dockerfile and Render configs"

# Push feature branch to GitHub (after approval)
git push -u origin feature/developer-5
```

### Opening a Pull Request
1. Open GitHub and navigate to your repository.
2. Click **Pull requests** > **New pull request**.
3. Set base: `develop` <- compare: `feature/developer-5`.
4. Ensure the GitHub Actions CI workflow passes all checks.
5. Review and merge into `develop`.

---

## 10. Render Deployment Instructions

Render is the designated cloud deployment platform.

### Option A: Deploy via Render Blueprint (`render.yaml`) — Recommended
1. Push your repository to GitHub.
2. Log into the [Render Dashboard](https://dashboard.render.com/).
3. Click **Blueprints** > **New Blueprint Instance**.
4. Connect your GitHub repository.
5. Render automatically reads `render.yaml`, provisions a **Render PostgreSQL database**, and sets up the **Web Service** with Gunicorn, WhiteNoise, and health checks.

### Option B: Deploy Manually as a Web Service
1. Create a **PostgreSQL** database on Render:
   * Name: `loan-db`
   * Region: Select closest region (e.g., Oregon)
   * Plan: Free
2. Create a **Web Service** on Render:
   * Connect your GitHub repository.
   * Environment: `Python 3`
   * Build Command:
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
     ```
   * Start Command:
     ```bash
     gunicorn loanproject.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
     ```
   * Health Check Path: `/healthz/`
3. Configure Environment Variables in Render Dashboard:
   * `DJANGO_DEBUG`: `False`
   * `DJANGO_SECRET_KEY`: `<Generate a random 50-character string>`
   * `DJANGO_ALLOWED_HOSTS`: `.onrender.com`
   * `CSRF_TRUSTED_ORIGINS`: `https://*.onrender.com`
   * `DATABASE_URL`: `<Internal Connection String from your Render PostgreSQL database>`
   * `PYTHON_VERSION`: `3.12.8`

---

## 11. Security & Production Checklist
* **DEBUG is False:** Production errors will never expose stack traces or environment variables.
* **Strict HTTPS Headers:** `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and `SECURE_HSTS_SECONDS` are automatically enforced when `DEBUG=False`.
* **Zero Hardcoded Secrets:** `SECRET_KEY` and database credentials must be provided via environment variables. Insecure default keys raise an `ImproperlyConfigured` exception in production.
* **WhiteNoise Static Serving:** Production static files are compressed and fingerprinted with cache headers.
* **Anti-Spoofing & Isolation:** Loan applications are strictly bound to `request.user`. Users can never query or mutate loans belonging to other borrowers.

---

## 12. Troubleshooting & FAQ

* **Issue: `403 Forbidden: CSRF verification failed` on Render**
  * *Fix:* Ensure `CSRF_TRUSTED_ORIGINS` includes your Render domain (e.g. `https://your-app-name.onrender.com`).
* **Issue: Database connection refused**
  * *Fix:* Confirm `DATABASE_URL` is set to the internal PostgreSQL connection string in the Render environment settings.
* **Issue: Static files not loading**
  * *Fix:* Verify that `python manage.py collectstatic --noinput` ran during the build step and that `whitenoise.middleware.WhiteNoiseMiddleware` is in `MIDDLEWARE`.

---

## 13. Known Limitations & Roadmap
* The ML service currently operates on the calibrated logistic underwriting scoring engine fallback because `loan_model.joblib` is not yet bundled. When a serialized model artifact is added to `loanapp/ml_models/loan_model.joblib`, the service will automatically detect and load it on startup without requiring any code changes.
