# Design: Flask Frontend + Bugfix + Mini API (Opzione B)

Data: 2026-10-06
Progetto: Progetto Semestre
Stile: Semplice e pulito (CSS puro)
Modalità: passo-passo, tutto insieme (backend fix poi frontend)

## 1. Contesto e problemi rilevati

- `router.py:34` funzione `idex()` rende `index.html`, file esistente `idex.html` (vuoto).
- `auth/auth.py:17` `url_for('dashboard')` inesistente, corretto `dashboard.dashboard`.
- `model/user.py` senza campo API key, ma `dashboard/dashboard.py:24` assegna `current_user.api_key` -> AttributeError.
- `model/key.py:7` istanzia un secondo `SQLAlchemy()` invece di `from model.db import db` -> tabella mai creata. Classe minuscola `key`, `created_at` senza default, nessuna relationship.
- `dashboard/dashboard.py:67` `add_balance()` senza return/redirect, usa `current_app.extensions.get('sqlalchemy')`, nessuna validazione importo.
- `dashboard()` non protetta, non passa balance/keys al template.
- Manca logout. Manca blueprint API (`api/` vuota).
- Template `login.html`, `register.html`, `idex.html`, `dashboard.html`, `docs.html` e `css/style.css` vuoti.

## 2. Architettura (approvata)

Flask + 3 blueprint: `auth`, `dashboard`, `api`.
DB: SQLite via `model/db.py` unico `db = SQLAlchemy()`.
Auth web: Flask-Login (sessioni). Auth API: header `X-API-Key`, solo hash SHA256 salvato.
Template: `template/` con `base.html` + `style.css` unico, flash messages.

Modelli finali:
- `User(id, username unique, password_hash)` 1-1 `Balance`, 1-N `ApiKey`
- `Balance(id, user_id unique FK, amount Numeric(12,2) default 0)`
- `ApiKey(id, user_id FK, api_key_hash unique 64, created_at default utcnow, name opzionale)`

## 3. Componenti e flusso (approvato)

Fix backend:
1. `model/key.py` -> classe `ApiKey`, `from model.db import db`, `created_at = default=datetime.utcnow`, `hash_api_key()` + `check_api_key()` con hmac.compare_digest, relationship `user`.
2. `model/user.py` -> aggiunge `api_keys = relationship(ApiKey, back_populates, cascade delete)`.
3. `auth/auth.py` -> fix redirect `dashboard.dashboard`, aggiunge `logout`, validazione form base, creazione `User` + `Balance` corretta.
4. `dashboard/dashboard.py` -> `from model.db import db`, `@login_required` su dashboard/balance, `gen_api_key()` crea riga ApiKey (mostra chiave in chiaro una sola volta via flash), `show_balance()` passa balance, `add_balance()` valida float>0, commit, redirect.
5. `router.py` -> `index()` rende `index.html`, registra `api_bp`, `db.create_all()`, `login_view = auth.login`.
6. `api/` -> `api_bp = Blueprint('api', url_prefix='/api')`, decoratore `require_api_key`, `GET /api/balance` -> `{"balance": str}`, `POST /api/add` con `{"amount": n}` -> aggiorna balance, errori JSON 401/400.

## 4. Frontend + errori + test (approvato)

Pagine (tutte estendono `base.html`):
- `index.html`: home + link login/register/dashboard/docs
- `login.html` / `register.html`: form username/password + flash
- `dashboard.html`: mostra balance, form add_balance, bottone genera key, lista keys (id, created_at, prefisso), link docs
- `docs.html`: documenta `GET /api/balance`, `POST /api/add` con esempi curl + X-API-Key

CSS: unico `style.css` semplice e pulito (layout centrato, nav, cards, form, flash), no framework.

Errori: pagine -> flash + redirect login; API -> JSON `{"error": ...}` 401 senza key, 400 importo invalido, 404 default.

Test manuale passo-passo:
1. `register` -> login -> dashboard vede 0.00
2. `add_balance 50` -> dashboard 50.00
3. `GenApiKey` -> copia chiave
4. `curl -H X-API-Key: <key> GET /api/balance` -> 50.00
5. `curl POST /api/add {"amount":10}` -> 60.00

## 5. Passi di implementazione

1. Fix modelli (key.py, user.py)
2. Fix auth + router
3. Fix dashboard
4. Nuovo blueprint api
5. base.html + style.css
6. index/login/register templates
7. dashboard/docs templates
8. Smoke test manuale

Fuori scope: paginazione keys, revoke UI avanzata, rate limit, Postgres, frontend JS.
