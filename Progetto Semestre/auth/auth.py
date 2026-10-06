from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from model.balance import Balance
from model.db import db
from model.spending_limit import SpendingLimit
from model.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login con username e password (GET mostra la pagina, POST la elabora)."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        # Verifica utente esistente + password corretta (confronto con hash).
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registrazione: crea l'utente con saldo 0 e limiti di default."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username e password obbligatori')
        elif User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            # Aggancia subito saldo e limiti di spesa (relazioni 1-1)
            new_user.balance = Balance(amount=0)
            new_user.spending_limit = SpendingLimit()
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful. Please log in.')
            return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Chiude la sessione dell'utente corrente."""
    logout_user()
    return redirect(url_for('index'))
