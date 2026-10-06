from datetime import datetime

from model.db import db


class AIModel(db.Model):
    """Modello AI esposto dal gateway (mappato su un modello NVIDIA NIM).

    I prezzi sono virtuali (CHF per 1M di token) e servono solo per
    il sistema di credito simulato del progetto.
    """
    __tablename__ = "ai_models"
    id = db.Column(db.Integer, primary_key=True)
    # "name" è l'ID pubblico usato dai client (es. nvidia/nemotron-3-super-120b-a12b)
    name = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    # Modello effettivo da passare a NVIDIA NIM (di solito coincide con name)
    nim_model = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    input_price = db.Column(db.Float, default=0.10)
    output_price = db.Column(db.Float, default=0.30)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    usages = db.relationship("Usage", back_populates="model")
