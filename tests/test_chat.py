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
