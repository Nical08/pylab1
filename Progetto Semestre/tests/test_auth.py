# Test delle pagine di autenticazione (registrazione, login, logout).


def test_home(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AI Gateway" in resp.data


def test_register_login_logout(client):
    # Registrazione: ci si aspetta il redirect al login con messaggio di successo
    resp = client.post("/register", data={"username": "mario", "password": "pw123456"},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert b"Registration successful" in resp.data

    # Login: si arriva alla dashboard
    resp = client.post("/login", data={"username": "mario", "password": "pw123456"},
                       follow_redirects=True)
    assert b"Saldo virtuale" in resp.data

    # Logout: si torna alla home
    resp = client.get("/logout", follow_redirects=True)
    assert b"AI Gateway" in resp.data


def test_dashboard_requires_login(client):
    # La dashboard è protetta: senza sessione si viene rediretti al login
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_wrong_password(client):
    client.post("/register", data={"username": "luigi", "password": "pw123456"})
    resp = client.post("/login", data={"username": "luigi", "password": "sbagliata"},
                       follow_redirects=True)
    assert b"Invalid username or password" in resp.data


def test_register_duplicate(client):
    client.post("/register", data={"username": "anna", "password": "pw123456"})
    resp = client.post("/register", data={"username": "anna", "password": "pw123456"},
                       follow_redirects=True)
    assert b"Username already exists" in resp.data


def test_register_requires_fields(client):
    # Username/password vuoti: la registrazione viene rifiutata
    resp = client.post("/register", data={"username": "", "password": ""},
                       follow_redirects=True)
    assert b"obbligatori" in resp.data
