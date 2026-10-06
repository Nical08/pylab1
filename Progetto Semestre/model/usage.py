from datetime import datetime

from model.db import db


class Usage(db.Model):
    """Una riga per ogni richiesta di chat completata.

    Registra token consumati e costo calcolato, e alimenta
    lo storico, il grafico e i limiti di spesa della dashboard.
    """
    __tablename__ = "usage"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # nullable: la key può essere eliminata ma lo storico resta
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_key.id'), nullable=True)
    model_id = db.Column(db.Integer, db.ForeignKey('ai_models.id'), nullable=True)
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="usages")
    api_key = db.relationship("ApiKey", back_populates="usages")
    model = db.relationship("AIModel", back_populates="usages")
