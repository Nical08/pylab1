from model.db import db
from model.key import ApiKey
from model.spending_limit import SpendingLimit
from model.user import User

# Funzioni di supporto condivise dai test.


def register_and_login(client, username, password="pw123456"):
    """Registra l'utente e fa subito login con il client di test."""
    client.post("/register", data={"username": username, "password": password})
    client.post("/login", data={"username": username, "password": password})


def add_balance(client, amount="20"):
    """Ricarica il saldo via form (richiede login già effettuato)."""
    return client.post("/add_balance", data={"amount": amount}, follow_redirects=True)


def create_api_key(app, username, raw="test-key-123"):
    """Crea direttamente nel DB una API key con valore noto,
    così i test possono usarla senza dover leggere il flash."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        db.session.add(ApiKey(user_id=user.id, api_key=raw))
        db.session.commit()
    return raw


def set_limits(app, username, weekly=10.0, monthly=50.0):
    """Imposta i limiti di spesa dell'utente (per i test sui blocchi 402)."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        lim = SpendingLimit.query.filter_by(user_id=user.id).first()
        if lim is None:
            lim = SpendingLimit(user_id=user.id)
            db.session.add(lim)
        lim.weekly_limit = weekly
        lim.monthly_limit = monthly
        db.session.commit()
