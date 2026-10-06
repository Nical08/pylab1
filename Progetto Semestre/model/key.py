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