# Progetto Semestre — AI Gateway

Piattaforma Flask che espone un gateway compatibile con l'SDK OpenAI verso modelli AI NVIDIA NIM, con registrazione/login, API key, credito virtuale, conteggio utilizzo, costo per richiesta e limiti di spesa settimanali/mensili.

Nota: pagamento e credito sono **completamente simulati**, nessuna carta reale.

## Requisiti

- Python 3.10+
- Una API key NVIDIA (https://build.nvidia.com) — facoltativa: senza chiave il gateway risponde in modalità mock

## Installazione

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Configurazione

```bash
copy .env.example .env        # Windows  (cp su Linux/macOS)
```

Variabili in `.env`:

```env
SECRET_KEY=change-me
SQLALCHEMY_DATABASE_URI=sqlite:///app.db
NVIDIA_API_KEY=your-api-key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

## Migrazioni e avvio

```bash
python -m flask --app router db upgrade
python router.py
```

App su http://localhost:5000

## API

Auth: `Authorization: Bearer <API key>` (creata dalla dashboard).

### GET /api/v1/models

```bash
curl http://localhost:5000/api/v1/models -H "Authorization: Bearer <key>"
```

### POST /api/v1/chat/completions

```bash
curl http://localhost:5000/api/v1/chat/completions \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-ai/deepseek-v4.1-flash", "messages": [{"role": "user", "content": "Ciao!"}]}'
```

### SDK OpenAI

```python
from openai import OpenAI

client = OpenAI(api_key="<key>", base_url="http://localhost:5000/api/v1")

response = client.chat.completions.create(
    model="deepseek-ai/deepseek-v4.1-flash",
    messages=[{"role": "user", "content": "Spiegami Flask"}]
)

print(response.choices[0].message.content)
```

## Test

```bash
pytest
```

- `tests/test_api.py` — API: auth con key, lista modelli, chat JSON e streaming SSE, errori 401/402/404, billing e limiti
- `tests/test_auth.py` — registrazione, login, logout, pagine protette
- `tests/test_ui.py` — Selenium (Chrome headless): registrazione, login, ricarica saldo, generazione API key; se Chrome non è disponibile i test UI vengono saltati automaticamente

## Flusso di una richiesta

Bearer key → modello attivo → limiti settimanali/mensili → NIM → calcolo costo → saldo → salvataggio Usage → risposta.

Modelli inclusi (seed): Nemotron 3 Super 120B, Laguna XS 2.1, Nemotron 3.5 Lightning.

Il gateway usa sempre lo streaming verso NVIDIA NIM (con retry sui 503): i client che non chiedono `stream` ricevono comunque una normale risposta JSON aggregata.

## Struttura

```text
auth/            login, register, logout
dashboard/       dashboard web (saldo, limiti, API key, docs)
api/             api.py (endpoint semplici), v1.py (gateway OpenAI-compatible)
model/           User, Balance, ApiKey, AIModel, Usage, SpendingLimit
services/        nim.py (chiamata NVIDIA / mock)
template/        pagine Jinja2
static/          CSS
migrations/      Flask-Migrate
```
