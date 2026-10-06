# Flask Frontend + Mini API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendere avviabile l'app Flask (fix bug) con frontend semplice in CSS puro e mini API con X-API-Key.

**Architecture:** 3 blueprint (`auth`, `dashboard`, `api`) su SQLite. Web con Flask-Login, API con hash SHA256. Template con `base.html` condiviso.

**Tech Stack:** Python 3.10 (system `python`), Flask 3.0.0, Flask-Login 0.6.3, Flask-SQLAlchemy 3.1.1, CSS puro.

---

### Task 1: Fix modelli (ApiKey + User)

**Files:**
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\model\key.py`
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\model\user.py`

- [ ] **Step 1: Riscrivi `model/key.py`**

```python
import hashlib
import hmac
from datetime import datetime

from model.db import db


class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    api_key_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship("User", back_populates="api_keys")

    def __init__(self, user_id, api_key):
        self.user_id = user_id
        self.api_key_hash = self.hash_api_key(api_key)

    @staticmethod
    def hash_api_key(api_key):
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    def check_api_key(self, api_key):
        return hmac.compare_digest(self.api_key_hash, self.hash_api_key(api_key))
```

- [ ] **Step 2: Aggiungi relationship in `model/user.py`**

```python
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from model.db import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.relationship(
        "Balance",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    api_keys = db.relationship(
        "ApiKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

- [ ] **Step 3: Verifica import**

Run: `python -c "from model.db import db; from model.user import User; from model.key import ApiKey; from model.balance import Balance; print('models ok')"`
Expected: `models ok` (da `C:\DatiAllievo\pytho\Progetto Semestre`)

- [ ] **Step 4: Commit**

```bash
git add "Progetto Semestre/model/key.py" "Progetto Semestre/model/user.py"
git commit -m "fix: ApiKey usa db condiviso + relationship User"
```

### Task 2: Fix auth + router

**Files:**
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\auth\auth.py`
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\router.py`

- [ ] **Step 1: Riscrivi `auth/auth.py`**

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from model.balance import Balance
from model.db import db
from model.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard.dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username e password obbligatori')
        elif User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            new_user.balance = Balance(amount=0)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful. Please log in.')
            return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
```

- [ ] **Step 2: Riscrivi `router.py`**

```python
import os
import secrets

from flask import Flask, render_template
from flask_login import LoginManager

from auth.auth import auth_bp
from model.db import db
from model.user import User
from dashboard.dashboard import dashboard_bp
from api.api import api_bp

app = Flask(__name__, template_folder="template")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_bp)

with app.app_context():
    db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
```

- [ ] **Step 3: Verifica avvio**

Run: `python -c "import router; print('router ok')"`
Expected: `router ok` senza AttributeError

- [ ] **Step 4: Commit**

```bash
git add "Progetto Semestre/auth/auth.py" "Progetto Semestre/router.py"
git commit -m "fix: redirect dashboard, logout, index route"
```

### Task 3: Fix dashboard

**Files:**
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\dashboard\dashboard.py`

- [ ] **Step 1: Riscrivi `dashboard/dashboard.py`**

```python
import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from model.balance import Balance
from model.db import db
from model.key import ApiKey
from model.user import User

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    balance = current_user.balance.amount if current_user.balance else 0
    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    return render_template('dashboard.html', balance=balance, keys=keys)


@dashboard_bp.route('/docs')
def docs():
    return render_template('docs.html')


@dashboard_bp.route('/GenApiKey', methods=['POST'])
@login_required
def gen_api_key():
    api_key = secrets.token_urlsafe(32)
    db.session.add(ApiKey(user_id=current_user.id, api_key=api_key))
    db.session.commit()
    flash(f'API key generata (copiala ora, non verrà più mostrata): {api_key}')
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/balance')
@login_required
def ShowBalance():
    balance = current_user.balance.amount if current_user.balance else 0
    return render_template('dashboard.html', balance=balance,
                           keys=ApiKey.query.filter_by(user_id=current_user.id).all())


@dashboard_bp.route('/add_balance', methods=['POST'])
@login_required
def add_balance():
    try:
        amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Importo non valido')
        return redirect(url_for('dashboard.dashboard'))
    if amount <= 0:
        flash('Importo deve essere positivo')
        return redirect(url_for('dashboard.dashboard'))
    user = db.session.get(User, current_user.id)
    if user.balance is None:
        user.balance = Balance(amount=amount)
    else:
        user.balance.amount = float(user.balance.amount) + amount
    db.session.commit()
    flash(f'Aggiunti {amount:.2f}')
    return redirect(url_for('dashboard.dashboard'))
```

- [ ] **Step 2: Verifica**

Run: `python -c "import dashboard.dashboard; print('dashboard ok')"`
Expected: `dashboard ok`

- [ ] **Step 3: Commit**

```bash
git add "Progetto Semestre/dashboard/dashboard.py"
git commit -m "fix: dashboard con ApiKey hash, validazione balance"
```

### Task 4: Mini API con X-API-Key

**Files:**
- Create: `C:\DatiAllievo\pytho\Progetto Semestre\api\api.py`
- Create: `C:\DatiAllievo\pytho\Progetto Semestre\api\__init__.py` (vuoto)

- [ ] **Step 1: Crea `api/__init__.py` vuoto**
- [ ] **Step 2: Crea `api/api.py`**

```python
from functools import wraps

from flask import Blueprint, request, jsonify

from model.balance import Balance
from model.db import db
from model.key import ApiKey
from model.user import User

api_bp = Blueprint('api', __name__, url_prefix='/api')


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        raw = request.headers.get('X-API-Key', '')
        if not raw:
            return jsonify({"error": "missing X-API-Key"}), 401
        key_hash = ApiKey.hash_api_key(raw)
        key = ApiKey.query.filter_by(api_key_hash=key_hash).first()
        if key is None:
            return jsonify({"error": "invalid api key"}), 401
        user = db.session.get(User, key.user_id)
        if user is None:
            return jsonify({"error": "user not found"}), 401
        return f(user, *args, **kwargs)
    return decorated


@api_bp.route('/balance', methods=['GET'])
@require_api_key
def api_balance(user):
    amount = float(user.balance.amount) if user.balance else 0.0
    return jsonify({"username": user.username, "balance": f"{amount:.2f}"})


@api_bp.route('/add', methods=['POST'])
@require_api_key
def api_add(user):
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({"error": "amount non valido"}), 400
    if amount <= 0:
        return jsonify({"error": "amount deve essere positivo"}), 400
    if user.balance is None:
        user.balance = Balance(amount=amount)
    else:
        user.balance.amount = float(user.balance.amount) + amount
    db.session.commit()
    return jsonify({"balance": f"{float(user.balance.amount):.2f}"})
```

- [ ] **Step 3: Verifica**

Run: `python -c "from api.api import api_bp; print('api ok')"`
Expected: `api ok`

- [ ] **Step 4: Commit**

```bash
git add "Progetto Semestre/api/api.py" "Progetto Semestre/api/__init__.py"
git commit -m "feat: mini API balance con X-API-Key"
```

### Task 5: base.html + style.css

**Files:**
- Create: `C:\DatiAllievo\pytho\Progetto Semestre\template\base.html`
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\template\css\style.css`

- [ ] **Step 1: Crea `template/base.html`**

```html
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Progetto Semestre{% endblock %}</title>
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
<nav>
<a href="{{ url_for('index') }}">Home</a>
<a href="{{ url_for('dashboard.dashboard') }}">Dashboard</a>
<a href="{{ url_for('dashboard.docs') }}">Docs API</a>
{% if current_user.is_authenticated %}
<span>Ciao, {{ current_user.username }}</span>
<a href="{{ url_for('auth.logout') }}">Logout</a>
{% else %}
<a href="{{ url_for('auth.login') }}">Login</a>
<a href="{{ url_for('auth.register') }}">Registrati</a>
{% endif %}
</nav>
<main>
{% with messages = get_flashed_messages() %}
{% if messages %}
<ul class="flash">
{% for m in messages %}<li>{{ m }}</li>{% endfor %}
</ul>
{% endif %}
{% endwith %}
{% block content %}{% endblock %}
</main>
</body>
</html>
```

NOTA: Flask serve `static/` di default, quindi sposta `template/css/style.css` in `static/css/style.css` con:

Run: `New-Item -ItemType Directory -Force -Path static/css; Copy-Item template/css/style.css static/css/style.css -Force`

- [ ] **Step 2: Scrivi `static/css/style.css`**

```css
body { font-family: system-ui, sans-serif; margin: 0; background: #f6f6f6; color: #222; }
nav { background: #222; padding: 12px; display: flex; gap: 12px; align-items: center; }
nav a { color: white; text-decoration: none; }
nav span { color: #ccc; margin-left: auto; }
main { max-width: 800px; margin: 24px auto; padding: 0 16px; }
.card { background: white; padding: 16px; border-radius: 8px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
form { display: flex; flex-direction: column; gap: 8px; max-width: 320px; }
input, button { padding: 8px; font-size: 1rem; }
button { background: #222; color: white; border: 0; border-radius: 4px; cursor: pointer; }
.flash { background: #fff3cd; padding: 12px; border-radius: 4px; list-style: none; }
code { background: #eee; padding: 2px 4px; border-radius: 4px; }
```

- [ ] **Step 3: Commit**

```bash
git add "Progetto Semestre/template/base.html" "Progetto Semestre/static/css/style.css"
git commit -m "feat: base layout + css semplice"
```

### Task 6: index + login + register

**Files:**
- Create: `C:\DatiAllievo\pytho\Progetto Semestre\template\index.html`
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\template\login.html`
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\template\register.html`

- [ ] **Step 1: Crea `template/index.html`**

```html
{% extends "base.html" %}
{% block title %}Home{% endblock %}
{% block content %}
<div class="card">
<h2>Progetto Semestre</h2>
<p>Gestisci saldo e API key. Vai alla <a href="{{ url_for('dashboard.dashboard') }}">Dashboard</a> o leggi i <a href="{{ url_for('dashboard.docs') }}">Docs API</a>.</p>
</div>
{% endblock %}
```

- [ ] **Step 2: Scrivi `template/login.html`**

```html
{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="card">
<h2>Login</h2>
<form method="post">
<input name="username" placeholder="username" required>
<input name="password" type="password" placeholder="password" required>
<button type="submit">Entra</button>
</form>
<p>Non hai account? <a href="{{ url_for('auth.register') }}">Registrati</a></p>
</div>
{% endblock %}
```

- [ ] **Step 3: Scrivi `template/register.html`**

```html
{% extends "base.html" %}
{% block title %}Registrati{% endblock %}
{% block content %}
<div class="card">
<h2>Registrati</h2>
<form method="post">
<input name="username" placeholder="username" required>
<input name="password" type="password" placeholder="password" required>
<button type="submit">Crea account</button>
</form>
</div>
{% endblock %}
```

- [ ] **Step 4: Smoke test**

Run: `python -c "from router import app; c=app.test_client(); print(c.get('/').status_code, c.get('/login').status_code, c.get('/register').status_code)"`
Expected: `200 200 200`

- [ ] **Step 5: Commit**

```bash
git add "Progetto Semestre/template/index.html" "Progetto Semestre/template/login.html" "Progetto Semestre/template/register.html"
git commit -m "feat: template index login register"
```

### Task 7: dashboard + docs

**Files:**
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\template\dashboard.html`
- Modify: `C:\DatiAllievo\pytho\Progetto Semestre\template\docs.html`

- [ ] **Step 1: Scrivi `template/dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="card">
<h2>Saldo: {{ balance }}</h2>
<form action="{{ url_for('dashboard.add_balance') }}" method="post">
<input name="amount" type="number" step="0.01" min="0.01" placeholder="10.00" required>
<button type="submit">Aggiungi saldo</button>
</form>
</div>
<div class="card">
<h3>API Key</h3>
<form action="{{ url_for('dashboard.gen_api_key') }}" method="post">
<button type="submit">Genera nuova key</button>
</form>
{% if keys %}
<ul>
{% for k in keys %}<li>#{{ k.id }} - {{ k.created_at }} - {{ k.api_key_hash[:12] }}...</li>{% endfor %}
</ul>
{% else %}
<p>Nessuna key ancora.</p>
{% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Scrivi `template/docs.html`**

```html
{% extends "base.html" %}
{% block title %}Docs API{% endblock %}
{% block content %}
<div class="card">
<h2>Docs API</h2>
<p>Usa header <code>X-API-Key</code>.</p>
<h3>GET /api/balance</h3>
<pre><code>curl -H "X-API-Key: &lt;key&gt;" http://localhost:5000/api/balance</code></pre>
<h3>POST /api/add</h3>
<pre><code>curl -X POST -H "Content-Type: application/json" -H "X-API-Key: &lt;key&gt;" -d '{"amount": 10}' http://localhost:5000/api/add</code></pre>
</div>
{% endblock %}
```

- [ ] **Step 3: Test manuale register->login->add->key->curl api con `python router.py`**
- [ ] **Step 4: Commit**

```bash
git add "Progetto Semestre/template/dashboard.html" "Progetto Semestre/template/docs.html"
git commit -m "feat: template dashboard docs"
```

### Task 8: Verifica finale

- [ ] **Step 1: Avvia `python router.py`, prova flusso completo**
- [ ] **Step 2: Rimuovi/rinomina `template/idex.html` in `index.html` se duplicato**
- [ ] **Step 3: Commit finale + riepilogo**
