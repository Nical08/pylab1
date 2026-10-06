from functools import wraps

from flask import Blueprint, request, jsonify

from model.balance import Balance
from model.db import db
from model.key import ApiKey
from model.user import User

api_bp = Blueprint('api', __name__, url_prefix='/api')


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        raw = request.headers.get('X-API-Key', '')
        if not raw:
            return jsonify({"error": "missing X-API-Key"}), 401
        key_hash = ApiKey.hash_api_key(raw)
        key = ApiKey.query.filter_by(api_key_hash=key_hash).first()
        if key is None:
            return jsonify({"error": "invalid api key"}), 401
        user = db.session.get(User, key.user_id)
        if user is None:
            return jsonify({"error": "user not found"}), 401
        return f(user, *args, **kwargs)
    return decorated


@api_bp.route('/balance', methods=['GET'])
@require_api_key
def api_balance(user):
    amount = float(user.balance.amount) if user.balance else 0.0
    return jsonify({"username": user.username, "balance": f"{amount:.2f}"})


@api_bp.route('/add', methods=['POST'])
@require_api_key
def api_add(user):
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({"error": "amount non valido"}), 400
    if amount <= 0:
        return jsonify({"error": "amount deve essere positivo"}), 400
    if user.balance is None:
        user.balance = Balance(amount=amount)
    else:
        user.balance.amount = float(user.balance.amount) + amount
    db.session.commit()
    return jsonify({"balance": f"{float(user.balance.amount):.2f}"})
