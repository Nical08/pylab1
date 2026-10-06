import json
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, Response, stream_with_context
from sqlalchemy import func

from model.ai_model import AIModel
from model.db import db
from model.key import ApiKey
from model.spending_limit import SpendingLimit
from model.usage import Usage
from model.user import User
from services.nim import send_chat_completion, stream_chat_completion

# Gateway compatibile con l'SDK OpenAI: /api/v1/models e /api/v1/chat/completions
api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


def err(message, typ, code, status):
    """Errore nel formato OpenAI: {"error": {"message", "type", "code"}}."""
    return jsonify({"error": {"message": message, "type": typ, "code": code}}), status


def get_key():
    """Legge l'header "Authorization: Bearer <key>" e trova la key nel DB (per hash)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    raw = auth[7:].strip()
    return ApiKey.query.filter_by(api_key_hash=ApiKey.hash_api_key(raw)).first()


def calc_cost(prompt_tokens, completion_tokens, input_price, output_price):
    """Costo in CHF virtuali: prezzo per 1M di token, quindi / 1.000.000."""
    return prompt_tokens / 1_000_000 * input_price + completion_tokens / 1_000_000 * output_price


def spent_since(user_id, days):
    """Spesa totale dell'utente negli ultimi N giorni (per i limiti)."""
    since = datetime.utcnow() - timedelta(days=days)
    total = db.session.query(func.coalesce(func.sum(Usage.cost), 0.0)).filter(
        Usage.user_id == user_id, Usage.created_at >= since).scalar()
    return float(total or 0.0)


def prompt_estimate(messages):
    """Stima grezza dei token di prompt (usata per il controllo saldo in streaming)."""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        total += len(str(content).split())
    return total + 8


def sse(payload):
    """Formatta un evento Server-Sent Events: "data: {json}\\n\\n"."""
    return f"data: {json.dumps(payload)}\n\n"


def chat_chunk(chat_id, created, model_name, delta, finish_reason=None, usage=None):
    """Costruisce un chunk di streaming nel formato OpenAI."""
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_name,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        chunk["usage"] = usage
    return chunk


@api_v1_bp.route('/models', methods=['GET'])
def list_models():
    """Elenca i modelli attivi nel formato OpenAI {"object": "list"}."""
    rec = get_key()
    if rec is None:
        return err("Invalid API key", "authentication_error", "invalid_api_key", 401)
    models = AIModel.query.filter_by(active=True).all()
    return jsonify({
        "object": "list",
        "data": [{"id": m.name, "object": "model"} for m in models],
    })


@api_v1_bp.route('/chat/completions', methods=['POST'])
def chat_completions():
    """Endpoint principale: verifica key, modello, limiti, saldo,
    chiama NIM, registra usage+costo e scala il saldo."""
    rec = get_key()
    if rec is None:
        return err("Invalid API key", "authentication_error", "invalid_api_key", 401)

    data = request.get_json(silent=True) or {}
    is_stream = bool(data.get("stream"))
    model_name = data.get("model", "")
    messages = data.get("messages", [])
    try:
        temperature = float(data.get("temperature", 1.0))
        top_p = float(data.get("top_p", 1.0))
        # Default alto: i modelli "reasoning" consumano molti token per pensare
        max_tokens = int(data.get("max_tokens", 4096))
    except (TypeError, ValueError):
        return err("Invalid request parameters", "invalid_request_error", "invalid_parameters", 400)

    # Modello richiesto: deve esistere ed essere attivo
    model = AIModel.query.filter_by(name=model_name, active=True).first()
    if model is None:
        return err("Model not found", "not_found", "model_not_found", 404)

    user = db.session.get(User, rec.user_id)
    if user is None:
        return err("Permission denied", "auth", "inactive_user", 403)

    # Limiti di spesa: 7 giorni (settimanale) e 30 giorni (mensile)
    lim = SpendingLimit.query.filter_by(user_id=user.id).first()
    if lim:
        if spent_since(user.id, 7) >= lim.weekly_limit:
            return err("Weekly spending limit exceeded", "billing_limit", "weekly_limit_exceeded", 402)
        if spent_since(user.id, 30) >= lim.monthly_limit:
            return err("Monthly spending limit exceeded", "billing_limit", "monthly_limit_exceeded", 402)
    nim_name = model.nim_model or model.name

    # ---------- Modalità streaming (SSE) ----------
    if is_stream:
        # Prima del via controlliamo il saldo con una stima worst-case
        # (prompt stimato + tutti i max_tokens), perché il costo vero
        # si conosce solo alla fine dello stream.
        balance = user.balance
        worst_case = calc_cost(prompt_estimate(messages), max_tokens,
                               model.input_price, model.output_price)
        if balance is None or float(balance.amount) < worst_case:
            return err("Insufficient virtual balance", "billing", "insufficient_balance", 402)
        chat_id = f"chatcmpl-{secrets.token_hex(12)}"
        created = int(datetime.utcnow().timestamp())

        def generate():
            """Generatore SSE: inoltra i chunk al client e alla fine
            registra Usage e scala il saldo."""
            prompt_tokens = completion_tokens = 0
            finish_reason = "stop"
            try:
                for event in stream_chat_completion(
                        nim_name, messages, temperature, top_p, max_tokens):
                    if event["type"] == "delta":
                        if event.get("kind") == "reasoning":
                            # Il "pensiero" viene passato nel campo reasoning_content
                            yield sse(chat_chunk(chat_id, created, model.name,
                                                 {"reasoning_content": event["content"]}))
                        else:
                            yield sse(chat_chunk(chat_id, created, model.name,
                                                 {"content": event["content"]}))
                    elif event["type"] == "finish":
                        finish_reason = event["finish_reason"]
                    elif event["type"] == "usage":
                        prompt_tokens = event["prompt_tokens"]
                        completion_tokens = event["completion_tokens"]
            except Exception as e:
                # Errore a stream già iniziato: lo comunichiamo come evento SSE
                yield sse({
                    "error": {
                        "message": f"NIM service error: {e}",
                        "type": "server",
                        "code": "nim_error",
                    }
                })
                yield "data: [DONE]\n\n"
                return
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
            # Chunk finale: finish_reason reale + usage
            yield sse(chat_chunk(chat_id, created, model.name, {}, finish_reason, usage))
            yield "data: [DONE]\n\n"
            # Fatturazione a stream concluso
            cost = calc_cost(prompt_tokens, completion_tokens,
                             model.input_price, model.output_price)
            db.session.add(Usage(
                user_id=user.id, api_key_id=rec.id, model_id=model.id,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens, cost=cost))
            if user.balance is not None:
                user.balance.amount = float(user.balance.amount) - cost
            db.session.commit()

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            # no-cache: evita che proxy/browser bufferizzino lo stream
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ---------- Modalità normale (JSON) ----------
    # Internamente passa comunque dallo streaming (send_chat_completion aggrega)
    try:
        result = send_chat_completion(nim_name, messages, temperature, top_p, max_tokens)
    except Exception as e:
        return err(f"NIM service error: {e}", "server", "nim_error", 502)
    cost = calc_cost(result["prompt_tokens"], result["completion_tokens"],
                     model.input_price, model.output_price)
    balance = user.balance
    if balance is None or float(balance.amount) < cost:
        return err("Insufficient virtual balance", "billing", "insufficient_balance", 402)
    usage = Usage(
        user_id=user.id,
        api_key_id=rec.id,
        model_id=model.id,
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["prompt_tokens"] + result["completion_tokens"],
        cost=cost,
    )
    db.session.add(usage)
    balance.amount = float(balance.amount) - cost
    db.session.commit()
    return jsonify({
        "id": f"chatcmpl-{usage.id}",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": model.name,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result["content"]},
            "finish_reason": result.get("finish_reason") or "stop",
        }],
        "usage": {
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "total_tokens": result["prompt_tokens"] + result["completion_tokens"],
        },
    })
