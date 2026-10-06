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