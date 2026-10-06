from model.db import db


class Balance(db.Model):
    """Saldo virtuale dell'utente (simulato, nessun pagamento reale)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    # Float (non Numeric) per non arrotondare i costi molto piccoli (< 1 centesimo).
    amount = db.Column(db.Float, nullable=False, default=0)
    user = db.relationship("User", back_populates="balance")
