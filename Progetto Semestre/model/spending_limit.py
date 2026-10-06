from datetime import datetime

from model.db import db


class SpendingLimit(db.Model):
    """Limiti di spesa settimanali e mensili dell'utente.

    Prima di ogni richiesta il gateway confronta la spesa degli
    ultimi 7/30 giorni con questi valori: se superati risponde 402.
    """
    __tablename__ = "spending_limits"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    weekly_limit = db.Column(db.Float, default=10.0)
    monthly_limit = db.Column(db.Float, default=50.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User", back_populates="spending_limit")
