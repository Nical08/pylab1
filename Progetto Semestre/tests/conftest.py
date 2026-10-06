import os
import socket
import tempfile
import threading

import pytest

# IMPORTANTE: le variabili d'ambiente vanno impostate PRIMA di importare
# router, perché router legge la configurazione all'import.
# Usiamo un DB temporaneo (così i test non toccano app.db) e la modalità
# mock di NIM (NVIDIA_API_KEY vuota): niente chiamate di rete.
_tmpdir = tempfile.mkdtemp(prefix="aigw_test_")
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    _tmpdir, "test.db").replace(os.sep, "/")
os.environ["NVIDIA_API_KEY"] = ""
os.environ["SECRET_KEY"] = "test-secret"

import router
from model.db import db
from model.user import User
from werkzeug.serving import make_server


@pytest.fixture(scope="session")
def app():
    """App Flask per i test: crea le tabelle nel DB temporaneo
    e inserisce i modelli finti (seed)."""
    with router.app.app_context():
        db.create_all()
        router.seed_ai_models()
    router.app.config["TESTING"] = True
    return router.app


@pytest.fixture()
def client(app):
    """Client HTTP di Flask per simulare richieste senza avviare il server."""
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_users(app):
    """Pulizia automatica dopo ogni test: elimina gli utenti creati
    (le relazioni con cascade rimuovono saldo, key, usage e limiti)."""
    yield
    with app.app_context():
        for user in User.query.all():
            db.session.delete(user)
        db.session.commit()


def _free_port():
    """Trova una porta libera per il server dei test UI."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="session")
def live_server(app):
    """Avvia l'app su un server reale (thread separato) per Selenium."""
    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="session")
def driver():
    """Browser Chrome headless per i test UI.
    Se selenium o Chrome non sono disponibili, i test UI vengono saltati."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        pytest.skip("selenium non installato")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    try:
        drv = webdriver.Chrome(options=options)
    except Exception as exc:
        pytest.skip(f"Chrome non disponibile: {exc}")
    yield drv
    drv.quit()
