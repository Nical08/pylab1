import json

from tests.helpers import add_balance, create_api_key, register_and_login, set_limits

# Test del gateway /api/v1 (NIM è in modalità mock: nessuna chiamata reale).
MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _auth(raw):
    # Header di autenticazione compatibile OpenAI
    return {"Authorization": f"Bearer {raw}"}


def _setup(client, app, username, balance=None):
    """Crea utente (con eventuale saldo) e una API key con valore noto."""
    register_and_login(client, username)
    if balance is not None:
        add_balance(client, balance)
    return create_api_key(app, username, raw=f"key-{username}")


def test_models_requires_key(client):
    # Senza Authorization: 401
    assert client.get("/api/v1/models").status_code == 401


def test_models_invalid_key(client):
    # Key inesistente: 401 con codice "invalid_api_key"
    resp = client.get("/api/v1/models", headers=_auth("key-sbagliata"))
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_api_key"


def test_models_list(client, app):
    # Lista modelli nel formato OpenAI
    raw = _setup(client, app, "apiuser")
    resp = client.get("/api/v1/models", headers=_auth(raw))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["object"] == "list"
    assert len(data["data"]) == 3
    assert all(item["object"] == "model" for item in data["data"])


def test_chat_json_and_billing(client, app):
    # Chat normale (JSON): risposta mock, usage registrato, saldo scalato
    raw = _setup(client, app, "apiuser", balance="10")
    resp = client.post("/api/v1/chat/completions", headers=_auth(raw),
                       json={"model": MODEL,
                             "messages": [{"role": "user", "content": "Ciao"}]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"].startswith("[MOCK")
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] > 0

    with app.app_context():
        from model.usage import Usage
        from model.user import User
        user = User.query.filter_by(username="apiuser").first()
        assert Usage.query.filter_by(user_id=user.id).count() == 1
        assert float(user.balance.amount) < 10.0


def test_chat_stream_sse(client, app):
    # Streaming: risposta SSE con chunk OpenAI e [DONE] finale
    raw = _setup(client, app, "apiuser", balance="10")
    resp = client.post("/api/v1/chat/completions", headers=_auth(raw),
                       json={"model": MODEL, "stream": True,
                             "messages": [{"role": "user", "content": "Ciao stream"}]})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["Content-Type"]
    body = resp.get_data(as_text=True)
    lines = [line for line in body.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    assert '"object": "chat.completion.chunk"' in body

    # Ricostruisce il testo dai delta e recupera l'usage dal chunk finale
    content = ""
    usage = None
    for line in lines[:-1]:
        event = json.loads(line[6:])
        if event.get("usage"):
            usage = event["usage"]
        delta = (event.get("choices") or [{}])[0].get("delta", {})
        content += delta.get("content") or ""
    assert content.startswith("[MOCK")
    assert usage is not None and usage["total_tokens"] > 0


def test_chat_model_not_found(client, app):
    # Modello inesistente: 404
    raw = _setup(client, app, "apiuser", balance="10")
    resp = client.post("/api/v1/chat/completions", headers=_auth(raw),
                       json={"model": "modello/inesistente",
                             "messages": [{"role": "user", "content": "Ciao"}]})
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "model_not_found"


def test_chat_insufficient_balance(client, app):
    # Utente senza saldo: 402 anche in modalità non-stream
    raw = _setup(client, app, "apiuser")
    resp = client.post("/api/v1/chat/completions", headers=_auth(raw),
                       json={"model": MODEL,
                             "messages": [{"role": "user", "content": "Ciao"}]})
    assert resp.status_code == 402
    assert resp.get_json()["error"]["code"] == "insufficient_balance"


def test_chat_weekly_limit(client, app):
    # Con un limite settimanale piccolissimo: la prima richiesta passa,
    # la seconda viene bloccata (spesa accumulata >= limite)
    raw = _setup(client, app, "apiuser", balance="10")
    set_limits(app, "apiuser", weekly=0.000001, monthly=50)
    first = client.post("/api/v1/chat/completions", headers=_auth(raw),
                        json={"model": MODEL,
                              "messages": [{"role": "user", "content": "Ciao"}]})
    assert first.status_code == 200
    second = client.post("/api/v1/chat/completions", headers=_auth(raw),
                         json={"model": MODEL,
                               "messages": [{"role": "user", "content": "Ciao"}]})
    assert second.status_code == 402
    assert second.get_json()["error"]["code"] == "weekly_limit_exceeded"
