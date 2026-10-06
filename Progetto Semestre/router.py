import os
import secrets

from dotenv import load_dotenv

# Carica le variabili da .env PRIMA di leggere os.environ.
# load_dotenv non sovrascrive variabili già presenti nell'ambiente,
# quindi nei test possiamo forzare valori diversi (es. DB temporaneo).
load_dotenv()

from flask import Flask
from flask_login import LoginManager
from flask import render_template
from flask_migrate import Migrate
from sqlalchemy import inspect

# Blueprint dell'applicazione (auth = login/register, dashboard = pagine web,
# api = endpoint semplici, api.v1 = gateway compatibile OpenAI)
from auth.auth import auth_bp
from model.db import db
from model.user import User
from model.balance import Balance
from model.key import ApiKey
from model.ai_model import AIModel
from model.usage import Usage
from model.spending_limit import SpendingLimit
from dashboard.dashboard import dashboard_bp
from api.api import api_bp
from api.v1 import api_v1_bp

# Applicazione Flask con i template in "template/"
app = Flask(__name__, template_folder="template")

# Configurazione presa dall'ambiente (.env), con fallback sicuri.
# SECRET_KEY firma il cookie di sessione: senza, Flask ne genera una casuale a ogni avvio.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "SQLALCHEMY_DATABASE_URI", os.environ.get("DATABASE_URL", "sqlite:///app.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["NVIDIA_API_KEY"] = os.environ.get("NVIDIA_API_KEY", "")
app.config["NVIDIA_BASE_URL"] = os.environ.get(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
# Timeout di lettura verso NIM (secondi)
app.config["NIM_TIMEOUT"] = int(os.environ.get("NIM_TIMEOUT", "180"))

db.init_app(app)
# render_as_batch=True: necessario per le migrazioni su SQLite (ALTER TABLE simulato)
migrate = Migrate(app, db, render_as_batch=True)

# Flask-Login: pagina a cui rimandare gli utenti non autenticati
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    # Ricarica l'utente dalla sessione a ogni richiesta.
    return db.session.get(User, int(user_id))


# Registrazione dei blueprint con i rispettivi prefissi
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_bp)
app.register_blueprint(api_v1_bp)


def seed_ai_models():
    """Popola/aggiorna i modelli AI disponibili (idempotente).

    Viene eseguito a ogni avvio: crea i modelli mancanti, aggiorna
    prezzi/descrizioni e disattiva quelli non più in elenco.
    """
    wanted = [
        ("nvidia/nemotron-3-super-120b-a12b", "Nemotron 3 Super 120B",
         "Modello NVIDIA Nemotron 3 Super 120B via NIM.", 0.50, 1.50),
        ("poolside/laguna-xs-2.1", "Laguna XS 2.1",
         "Modello Poolside Laguna XS 2.1 via NIM.", 0.20, 0.60),
        ("nvidia/nemotron-3.5-lightning-30b-a3b", "Nemotron 3.5 Lightning",
         "Modello NVIDIA Nemotron 3.5 Lightning 30B via NIM.", 0.30, 0.90),
    ]
    names = [item[0] for item in wanted]
    for name, display, desc, inp, out in wanted:
        model = AIModel.query.filter_by(name=name).first()
        if model is None:
            db.session.add(AIModel(
                name=name, display_name=display, description=desc,
                nim_model=name, input_price=inp, output_price=out, active=True))
        else:
            model.display_name = display
            model.description = desc
            model.nim_model = name
            model.input_price = inp
            model.output_price = out
            model.active = True
    # I modelli non più in elenco vengono disattivati (non cancellati,
    # così lo storico Usage resta valido).
    for model in AIModel.query.filter(AIModel.name.notin_(names)).all():
        model.active = False
    db.session.commit()


with app.app_context():
    # Il seed gira solo se le migrazioni sono già state applicate
    # (altrimenti la tabella non esiste ancora).
    if inspect(db.engine).has_table("ai_models"):
        seed_ai_models()


@app.route('/')
def index():
    # Homepage: mostra i modelli attivi con relativi prezzi
    models = AIModel.query.filter_by(active=True).order_by(AIModel.id).all()
    return render_template('index.html', models=models)


if __name__ == '__main__':
    # debug=True attiva il reload automatico e il debugger (solo sviluppo)
    app.run(debug=True)
