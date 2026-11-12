"""Tests for the static /glossary endpoint (Phase 5)."""


async def test_glossary_returns_static_terms(client):
    response = await client.get("/glossary")
    assert response.status_code == 200

    terms = response.json()["terms"]
    assert len(terms) >= 10
    assert all(t["term"] and t["definition"] for t in terms)
    assert any(t["term"] == "VIX" for t in terms)
