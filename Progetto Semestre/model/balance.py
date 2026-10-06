from model.db import db


class Balance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    user = db.relationship("User", back_populates="balance")

    