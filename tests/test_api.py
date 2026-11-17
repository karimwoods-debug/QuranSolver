from __future__ import annotations


def test_health(make_client):
    with make_client() as client:
        body = client.get("/api/health").json()
    assert body["guided_mode"] is False
    assert body["counts"] == {"verses": 3, "hadith_total": 5, "hadith_authentic": 2}


def test_ask(make_client):
    with make_client() as client:
        r = client.post("/api/ask", json={"problem": "I need patience in hardship"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "search"
    assert body["verses"][0]["id"] == "Q:1:1"
    assert body["verses"][0]["url"] == "https://quran.com/1/1"


def test_ask_crisis(make_client):
    with make_client() as client:
        body = client.post("/api/ask", json={"problem": "I want to end my life"}).json()
    assert body["crisis"] is True
    assert body["crisis_resources"]


def test_ask_validation(make_client):
    with make_client() as client:
        assert client.post("/api/ask", json={"problem": ""}).status_code == 422


def test_verse_and_hadith_lookup(make_client):
    with make_client() as client:
        assert client.get("/api/verse/1/2").json()["reference"] == "Qur'an 1:2"
        assert client.get("/api/verse/9/9").status_code == 404
        assert client.get("/api/hadith/abudawud/10").json()["grade"] == "Sahih (Al-Albani)"
        assert client.get("/api/hadith/abudawud/11").status_code == 404  # weak: never served


def test_index_page(make_client):
    with make_client() as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "QuranSolver" in r.text
