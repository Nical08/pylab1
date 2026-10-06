import hashlib
import hmac
from datetime import datetime

from model.db import db


class ApiKey(db.Model):
    """API key personale dell'utente.

    Nel database viene salvato solo l'hash SHA-256: la chiave in chiaro
    viene mostrata una sola volta al momento della creazione.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    api_key_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship("User", back_populates="api_keys")
    usages = db.relationship("Usage", back_populates="api_key")

    def __init__(self, user_id, api_key):
        # Alla creazione si passa la chiave in chiaro, che viene subito hashed.
        self.user_id = user_id
        self.api_key_hash = self.hash_api_key(api_key)

    @staticmethod
    def hash_api_key(api_key):
        # SHA-256: veloce e deterministico, adatto a chiavi casuali lunghe.
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    def check_api_key(self, api_key):
        # Confronto a tempo costante per evitare timing attack.
        return hmac.compare_digest(self.api_key_hash, self.hash_api_key(api_key))
