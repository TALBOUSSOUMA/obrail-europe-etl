def test_list_dessertes_default(client):
    resp = client.get("/dessertes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert len(body["resultats"]) == body["limit"]


def test_list_dessertes_respects_limit(client):
    resp = client.get("/dessertes?limit=5")
    assert resp.status_code == 200
    assert len(resp.json()["resultats"]) == 5


def test_filter_by_service_type(client):
    resp = client.get("/dessertes?service_type=Nuit&limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert all(r["service_type"] == "Nuit" for r in body["resultats"])


def test_filter_by_ville_depart_is_case_insensitive(client):
    resp_lower = client.get("/dessertes?ville_depart=paris&limit=1")
    resp_upper = client.get("/dessertes?ville_depart=PARIS&limit=1")
    assert resp_lower.status_code == 200
    assert resp_lower.json()["total"] == resp_upper.json()["total"]
    assert resp_lower.json()["total"] > 0


def test_filter_by_pays_destination(client):
    resp = client.get("/dessertes?pays_destination=CH&limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert all(r["pays_destination"] == "CH" for r in body["resultats"])
    assert all(r["nom_pays_destination"] == "Suisse" for r in body["resultats"])


def test_filter_by_type_train_is_exact_not_partial(client):
    """Regression test: the frontend now offers 'Type de train' via a
    dropdown (exact values from /types-train), so the filter must match
    exactly - before this fix, 'Intercites' also matched 'Intercites de
    nuit' (partial ILIKE %...% search)."""
    resp = client.get("/dessertes?type_train=Intercites&limit=500")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert all(r["type_train"] == "Intercites" for r in body["resultats"])


def test_combined_filters_never_return_more_than_single_filter(client):
    total_nuit = client.get("/dessertes?service_type=Nuit&limit=1").json()["total"]
    total_nuit_fr = client.get("/dessertes?service_type=Nuit&pays_origine=FR&limit=1").json()["total"]
    assert total_nuit_fr <= total_nuit


def test_get_one_desserte_by_trip_id(client):
    trip_id = client.get("/dessertes?limit=1").json()["resultats"][0]["trip_id"]
    resp = client.get(f"/dessertes/{trip_id}")
    assert resp.status_code == 200
    assert resp.json()["trip_id"] == trip_id


def test_get_unknown_desserte_returns_404(client):
    resp = client.get("/dessertes/ce-trip-id-nexiste-pas")
    assert resp.status_code == 404


def test_limit_out_of_range_is_rejected(client):
    resp = client.get("/dessertes?limit=10000")
    assert resp.status_code == 422  # exceeds the max=500 defined in the API
