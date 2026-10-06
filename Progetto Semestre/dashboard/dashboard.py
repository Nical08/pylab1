from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import secrets

from model.balance import Balance
from model.db import db
from model.key import ApiKey
from model.user import User

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    balance = current_user.balance.amount if current_user.balance else 0
    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    return render_template('dashboard.html', balance=balance, keys=keys)

@dashboard_bp.route('/docs')
def docs():
    return render_template('docs.html')


@dashboard_bp.route('/GenApiKey', methods=['POST'])
@login_required
def gen_api_key():
    api_key = secrets.token_urlsafe(32)
    db.session.add(ApiKey(user_id=current_user.id, api_key=api_key))
    db.session.commit()
    flash(f'API key generata (copiala ora, non verrà più mostrata): {api_key}')
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/balance')
@login_required
def ShowBalance():
    balance = current_user.balance.amount if current_user.balance else 0
    return render_template('dashboard.html', balance=balance,
                           keys=ApiKey.query.filter_by(user_id=current_user.id).all())


@dashboard_bp.route('/add_balance', methods=['POST'])
@login_required
def add_balance():
    try:
        amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Importo non valido')
        return redirect(url_for('dashboard.dashboard'))
    if amount <= 0:
        flash('Importo deve essere positivo')
        return redirect(url_for('dashboard.dashboard'))
    user = db.session.get(User, current_user.id)
    if user.balance is None:
        user.balance = Balance(amount=amount)
    else:
        user.balance.amount = float(user.balance.amount) + amount
    db.session.commit()
    flash(f'Aggiunti {amount:.2f}')
    return redirect(url_for('dashboard.dashboard'))