from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from retro_sage import chat
from retro_sage.profile import build_profile
from retro_sage.scorer import recommend


def _response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason
    )


class FakeClient:
    """Sustituto del cliente de anthropic: captura kwargs y cuenta llamadas."""

    def __init__(self, response):
        self.calls: list[dict] = []
        self._response = response
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


@pytest.fixture
def candidatos(library):
    profile = build_profile(library)
    return profile, recommend(library, profile, top=chat.MAX_CANDIDATES)


def test_ask_un_solo_request_con_perfil_y_candidatos(library, candidatos, monkeypatch):
    profile, items = candidatos
    fake = FakeClient(_response("Terranigma es tu mejor opción."))
    monkeypatch.setattr(chat, "_client", lambda: fake)

    answer = chat.ask("algo como Chrono Trigger", profile, items, library)

    assert answer == "Terranigma es tu mejor opción."
    assert len(fake.calls) == 1  # control de coste: un request por invocación
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "Terranigma" in prompt  # candidatos del scorer local
    assert "rpg" in prompt  # perfil resumido
    assert "algo como Chrono Trigger" in prompt


def test_ask_respuesta_vacia_o_rechazo_es_chaterror(library, candidatos, monkeypatch):
    profile, items = candidatos
    monkeypatch.setattr(chat, "_client", lambda: FakeClient(_response("   ")))
    with pytest.raises(chat.ChatError):
        chat.ask("x", profile, items, library)

    monkeypatch.setattr(chat, "_client", lambda: FakeClient(_response("", stop_reason="refusal")))
    with pytest.raises(chat.ChatError):
        chat.ask("x", profile, items, library)


def test_explain_devuelve_razones_por_id(library, candidatos, monkeypatch):
    profile, items = candidatos
    payload = json.dumps({"reasons": [{"id": items[0]["id"], "reason": "Te va a encantar por X."}]})
    fake = FakeClient(_response(payload))
    monkeypatch.setattr(chat, "_client", lambda: fake)

    reasons = chat.explain(items, profile, library)

    assert reasons == {items[0]["id"]: "Te va a encantar por X."}
    assert len(fake.calls) == 1
    assert "format" in fake.calls[0]["output_config"]  # salida estructurada


def test_explain_formato_inesperado_es_chaterror(library, candidatos, monkeypatch):
    profile, items = candidatos
    monkeypatch.setattr(chat, "_client", lambda: FakeClient(_response("no soy json")))
    with pytest.raises(chat.ChatError):
        chat.explain(items, profile, library)


def _fake_gemini(monkeypatch, payload):
    """Activa el backend Gemini con un _post_json fake. Devuelve las llamadas."""
    monkeypatch.setenv("GEMINI_API_KEY", "clave-test")
    calls = []

    def post(url, body, headers):
        calls.append((url, body, headers))
        return payload

    monkeypatch.setattr(chat, "_post_json", post)
    return calls


def _gemini_text(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_gemini_ask_sin_dependencias(library, candidatos, monkeypatch):
    profile, items = candidatos
    calls = _fake_gemini(monkeypatch, _gemini_text("Terranigma, sin duda."))

    answer = chat.ask("algo épico", profile, items, library)

    assert answer == "Terranigma, sin duda."
    assert len(calls) == 1  # control de coste también en Gemini
    url, body, headers = calls[0]
    assert "gemini-2.5-flash" in url
    assert headers["x-goog-api-key"] == "clave-test"
    prompt = body["contents"][0]["parts"][0]["text"]
    assert "Terranigma" in prompt and "algo épico" in prompt


def test_gemini_explain_pide_json_estructurado(library, candidatos, monkeypatch):
    profile, items = candidatos
    payload = _gemini_text(
        json.dumps({"reasons": [{"id": items[0]["id"], "reason": "Por tus rpg."}]})
    )
    calls = _fake_gemini(monkeypatch, payload)

    reasons = chat.explain(items, profile, library)

    assert reasons == {items[0]["id"]: "Por tus rpg."}
    config = calls[0][1]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in config


def test_gemini_bloqueado_o_vacio_es_chaterror(library, candidatos, monkeypatch):
    profile, items = candidatos
    _fake_gemini(monkeypatch, {"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(chat.ChatError, match="SAFETY"):
        chat.ask("x", profile, items, library)


def test_flag_model_manda_sobre_el_default(library, candidatos, monkeypatch):
    profile, items = candidatos
    calls = _fake_gemini(monkeypatch, _gemini_text("ok"))
    chat.ask("x", profile, items, library, model="gemini-2.0-flash")
    assert "gemini-2.0-flash" in calls[0][0]


def test_fallo_del_sdk_se_convierte_en_chaterror(library, candidatos, monkeypatch):
    profile, items = candidatos

    class Roto:
        def __init__(self):
            self.messages = SimpleNamespace(create=self._boom)

        def _boom(self, **kwargs):
            raise RuntimeError("timeout simulado")

    monkeypatch.setattr(chat, "_client", lambda: Roto())
    with pytest.raises(chat.ChatError):
        chat.ask("x", profile, items, library)
