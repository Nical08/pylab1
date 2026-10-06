from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
import secrets

from model.balance import Balance
from model.db import db
from model.key import ApiKey
from model.spending_limit import SpendingLimit
from model.usage import Usage
from model.user import User

dashboard_bp = Blueprint('dashboard', __name__)

# Etichette dei giorni per il grafico (weekday(): 0 = lunedì)
WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']


def _keys():
    # API key dell'utente loggato, dalla più recente
    return ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()


def _spent_since(user_id, days):
    """Somma dei costi delle richieste degli ultimi N giorni."""
    since = datetime.utcnow() - timedelta(days=days)
    total = db.session.query(func.coalesce(func.sum(Usage.cost), 0.0)).filter(
        Usage.user_id == user_id, Usage.created_at >= since).scalar()
    return float(total or 0.0)


def _daily_chart(user_id, days=7):
    """Dati per il grafico CSS: spesa giornaliera degli ultimi 7 giorni.

    Ritorna label (giorno), valore in CHF e altezza percentuale della barra
    (minimo 6% per rendere visibili i giorni a zero).
    """
    today = datetime.utcnow().date()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    start = datetime.combine(day_list[0], datetime.min.time())
    rows = db.session.query(func.date(Usage.created_at), func.sum(Usage.cost)).filter(
        Usage.user_id == user_id, Usage.created_at >= start
    ).group_by(func.date(Usage.created_at)).all()
    by_day = {str(day): float(cost or 0.0) for day, cost in rows}
    values = [by_day.get(str(day), 0.0) for day in day_list]
    peak = max(values) if values else 0.0
    return [
        {
            'label': WEEKDAYS[day.weekday()],
            'value': value,
            'h': max(6, round(value / peak * 100)) if peak else 6,
        }
        for day, value in zip(day_list, values)
    ]


def _render_dashboard():
    """Prepara tutti i dati mostrati nella dashboard e renderizza il template."""
    balance = float(current_user.balance.amount) if current_user.balance else 0.0
    lim = SpendingLimit.query.filter_by(user_id=current_user.id).first()
    weekly_limit = lim.weekly_limit if lim else 10.0
    monthly_limit = lim.monthly_limit if lim else 50.0
    spent_week = _spent_since(current_user.id, 7)
    spent_month = _spent_since(current_user.id, 30)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return render_template(
        'dashboard.html',
        balance=balance,
        keys=_keys(),
        weekly_limit=weekly_limit,
        monthly_limit=monthly_limit,
        spent_week=spent_week,
        spent_month=spent_month,
        # Percentuali per le barre dei limiti (max 100%)
        week_pct=min(100, round(spent_week / weekly_limit * 100)) if weekly_limit else 0,
        month_pct=min(100, round(spent_month / monthly_limit * 100)) if monthly_limit else 0,
        total_requests=Usage.query.filter_by(user_id=current_user.id).count(),
        today_requests=Usage.query.filter(
            Usage.user_id == current_user.id, Usage.created_at >= today_start).count(),
        # Ultime 10 richieste per lo storico in tabella
        recent=Usage.query.filter_by(user_id=current_user.id)
                      .order_by(Usage.created_at.desc()).limit(10).all(),
        chart=_daily_chart(current_user.id),
    )


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return _render_dashboard()


@dashboard_bp.route('/docs')
def docs():
    # Pagina documentazione: elenca i modelli attivi col listino
    from model.ai_model import AIModel
    models = AIModel.query.filter_by(active=True).order_by(AIModel.id).all()
    return render_template('docs.html', models=models)


@dashboard_bp.route('/GenApiKey', methods=['POST'])
@login_required
def gen_api_key():
    """Genera una nuova API key e la mostra una sola volta via flash."""
    api_key = secrets.token_urlsafe(32)
    db.session.add(ApiKey(user_id=current_user.id, api_key=api_key))
    db.session.commit()
    flash(f'API key generata (copiala ora, non verrà più mostrata): {api_key}')
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/DeleteApiKey/<int:key_id>', methods=['POST'])
@login_required
def delete_api_key(key_id):
    """Elimina una key dell'utente (solo se gli appartiene)."""
    key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
    if key is None:
        flash('API key non trovata')
        return redirect(url_for('dashboard.dashboard'))
    # Sgancia lo storico: le richieste restano ma senza riferimento alla key
    Usage.query.filter_by(api_key_id=key.id).update({'api_key_id': None})
    db.session.delete(key)
    db.session.commit()
    flash('API key eliminata')
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/balance')
@login_required
def ShowBalance():
    return _render_dashboard()


@dashboard_bp.route('/add_balance', methods=['POST'])
@login_required
def add_balance():
    """Ricarica il saldo virtuale (simulata, nessun pagamento reale)."""
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
    flash(f'Aggiunti CHF {amount:.2f}')
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/limits', methods=['POST'])
@login_required
def set_limits():
    """Aggiorna i limiti di spesa settimanale e mensile."""
    lim = SpendingLimit.query.filter_by(user_id=current_user.id).first()
    if lim is None:
        lim = SpendingLimit(user_id=current_user.id)
        db.session.add(lim)
    try:
        weekly = float(request.form.get('weekly_limit', '10'))
        monthly = float(request.form.get('monthly_limit', '50'))
    except ValueError:
        flash('Limiti non validi')
        return redirect(url_for('dashboard.dashboard'))
    if weekly <= 0 or monthly <= 0:
        flash('I limiti devono essere positivi')
        return redirect(url_for('dashboard.dashboard'))
    lim.weekly_limit = weekly
    lim.monthly_limit = monthly
    db.session.commit()
    flash('Limiti di spesa aggiornati')
    return redirect(url_for('dashboard.dashboard'))
