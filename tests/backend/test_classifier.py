import httpx
import pytest

import classifier_runner as classifier


@pytest.mark.parametrize("content,expected", [
    ('{"label":"Human"}', {"label": "Human"}),
    ('```json\n{"label":"Human"}\n```', {"label": "Human"}),
    ('Here is the result: {"ai_probability":0.8}', {"ai_probability": 0.8}),
    ('not JSON', {}),
])
def test_model_output_parsing(content, expected):
    assert classifier._parse_json_loose(content) == expected


@pytest.mark.parametrize("judge,expected", [
    ({"label": "AI-likely", "ai_probability": 0.9}, {"classification": "AI", "accuracy": 0.9}),
    ({"label": "Human", "ai_probability": 0.1}, {"classification": "Human", "accuracy": 0.9}),
    ({"label": "Uncertain", "ai_probability": 0.6}, {"classification": "AI", "accuracy": 0.6}),
    ({"ai_probability": 2}, {"classification": "AI", "accuracy": 1.0}),
    ({"ai_probability": -1}, {"classification": "Human", "accuracy": 1.0}),
    ({}, {"classification": "Human", "accuracy": 0.5}),
])
def test_classification_and_confidence(judge, expected):
    assert classifier._collapse_to_two_fields(judge) == expected


async def test_ollama_request_and_response_contract(monkeypatch):
    def respond(request):
        import json
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["stream"] is False
        assert "test lyrics" in payload["messages"][1]["content"]
        return httpx.Response(200, json={"message": {"content": '{"ai_probability":0.9,"label":"AI-likely"}'}})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(classifier, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(classifier.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(respond), **kwargs))
    assert await classifier.process_task({"stage": "classify", "lyrics": "test lyrics"}) == {"classification": "AI", "accuracy": 0.9}


async def test_model_http_error_becomes_bad_gateway(monkeypatch):
    from fastapi import HTTPException
    client_class = httpx.AsyncClient
    monkeypatch.setattr(classifier, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(classifier.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(lambda request: httpx.Response(500)), **kwargs))
    with pytest.raises(HTTPException) as error:
        await classifier._ask_llm("text")
    assert error.value.status_code == 502
