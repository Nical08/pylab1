from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from model.db import db


class User(UserMixin, db.Model):
    """Utente della piattaforma.

    UserMixin aggiunge i metodi richiesti da Flask-Login
    (is_authenticated, get_id, ...) per gestire la sessione.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Relazioni 1-1 / 1-N con cascade: cancellando l'utente
    # vengono eliminati anche saldo, API key, consumi e limiti.
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
    usages = db.relationship(
        "Usage",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    spending_limit = db.relationship(
        "SpendingLimit",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        # Salva solo l'hash, mai la password in chiaro (Werkzeug).
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Confronta la password inserita con l'hash salvato.
        return check_password_hash(self.password_hash, password)
