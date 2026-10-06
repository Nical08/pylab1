import json
import time

import requests
from flask import current_app

# Servizio NIM: unico punto che parla con NVIDIA.
# L'app usa SEMPRE lo streaming verso NIM (più robusto: i token arrivano
# man mano e non si aspetta l'intera risposta), poi aggrega se serve.


def _text_of(content):
    """Normalizza il contenuto di un messaggio (stringa o lista multimodale)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content or "")


def _delta_piece(delta):
    """Estrae il testo da un delta SSE.

    I modelli "reasoning" (es. Nemotron) mandano il pensiero in
    reasoning_content e la risposta finale in content: distinguiamo i due.
    """
    piece = delta.get("content")
    if isinstance(piece, list):
        piece = " ".join(
            part.get("text", "")
            for part in piece
            if isinstance(part, dict)
        )
    if piece:
        return piece, "content"
    reasoning = delta.get("reasoning_content")
    if reasoning:
        return reasoning, "reasoning"
    return "", "content"


def _mock_response(nim_model, messages):
    """Risposta finta usata quando manca la chiave NVIDIA (sviluppo/test)."""
    last = _text_of(messages[-1].get("content", "")) if messages else "Ciao"
    text = f"[MOCK {nim_model}] Hai detto: {last}"
    prompt_tokens = sum(len(_text_of(m.get("content", "")).split()) for m in messages) + 8
    completion_tokens = len(text.split()) + 5
    return {
        "content": text,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def _config():
    # Configurazione arrivata da .env tramite router.py
    api_key = current_app.config.get("NVIDIA_API_KEY", "")
    base_url = current_app.config.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    timeout = current_app.config.get("NIM_TIMEOUT", 180)
    return api_key, base_url, timeout


def _is_mock(api_key):
    # Consideriamo "mock" una chiave assente o il placeholder dell'esempio
    return not api_key or api_key == "your-api-key"


# Status temporanei di NIM (worker occupati, rate limit...): vale la pena riprovare
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _post_stream(base_url, api_key, payload, timeout, attempts=3):
    """POST in streaming verso NIM con retry sui 503/429 e sugli errori di rete."""
    last_error = None
    for i in range(attempts):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=(15, timeout),
                stream=True,
            )
        except requests.RequestException as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (i + 1))
            continue
        if resp.status_code in RETRY_STATUSES:
            last_error = f"NIM HTTP {resp.status_code}: {resp.text[:200]}"
            resp.close()
            time.sleep(1.5 * (i + 1))
            continue
        return resp
    raise RuntimeError(f"{last_error} (dopo {attempts} tentativi)")


def stream_chat_completion(nim_model, messages, temperature=1.0, top_p=1.0, max_tokens=4096):
    """Generatore di eventi (streaming verso NIM):
    {"type": "delta", "content": str, "kind": "content"|"reasoning"}
    {"type": "finish", "finish_reason": str}
    {"type": "usage", "prompt_tokens": int, "completion_tokens": int, "estimated": bool}
    """
    api_key, base_url, timeout = _config()
    if _is_mock(api_key):
        # Modalità mock: simula lo stream a pezzetti per testare l'UI
        mock = _mock_response(nim_model, messages)
        text = mock["content"]
        for i in range(0, len(text), 16):
            yield {"type": "delta", "content": text[i:i + 16], "kind": "content"}
        yield {"type": "finish", "finish_reason": "stop"}
        yield {
            "type": "usage",
            "prompt_tokens": mock["prompt_tokens"],
            "completion_tokens": mock["completion_tokens"],
            "estimated": False,
        }
        return
    resp = _post_stream(base_url, api_key, {
        "model": nim_model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": True,
        # Chiediamo a NIM di includere l'usage nell'ultimo evento
        "stream_options": {"include_usage": True},
    }, timeout)
    if resp.status_code != 200:
        body = resp.text[:300]
        resp.close()
        raise RuntimeError(f"NIM HTTP {resp.status_code}: {body}")
    content_text = ""
    reasoning_text = ""
    usage = None
    finish_reason = None
    try:
        # Formato SSE: righe "data: {json}" fino a "data: [DONE]"
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            choices = event.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                piece, kind = _delta_piece(delta)
                if piece:
                    if kind == "reasoning":
                        reasoning_text += piece
                    else:
                        content_text += piece
                    yield {"type": "delta", "content": piece, "kind": kind}
                # finish_reason reale: "stop" se completo, "length" se troncato
                if choices[0].get("finish_reason"):
                    finish_reason = choices[0]["finish_reason"]
            if event.get("usage"):
                usage = event["usage"]
    finally:
        resp.close()
    yield {"type": "finish", "finish_reason": finish_reason or "stop"}
    if usage:
        # Token ufficiali forniti da NIM
        yield {
            "type": "usage",
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "estimated": False,
        }
    else:
        # Fallback: stima dai token "parlati" (usata solo se NIM non li manda)
        prompt_tokens = sum(len(_text_of(m.get("content", "")).split()) for m in messages) + 8
        completion_tokens = len((content_text + " " + reasoning_text).split()) + 1
        yield {
            "type": "usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated": True,
        }


def send_chat_completion(nim_model, messages, temperature=1.0, top_p=1.0, max_tokens=4096):
    """Versione non-stream per i client che non chiedono stream:
    internamente usa SEMPRE lo streaming verso NIM e aggrega la risposta.

    Vantaggio: niente timeout da "risposta completa" e retry automatici.
    """
    api_key, _, _ = _config()
    if _is_mock(api_key):
        return _mock_response(nim_model, messages)
    text = ""
    prompt_tokens = completion_tokens = 0
    finish_reason = "stop"
    for event in stream_chat_completion(nim_model, messages, temperature, top_p, max_tokens):
        if event["type"] == "delta":
            # Nella risposta finale includiamo solo il testo vero, non il reasoning
            if event.get("kind") == "content":
                text += event["content"]
        elif event["type"] == "finish":
            finish_reason = event["finish_reason"]
        elif event["type"] == "usage":
            prompt_tokens = event["prompt_tokens"]
            completion_tokens = event["completion_tokens"]
    return {
        "content": text,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "finish_reason": finish_reason,
    }
