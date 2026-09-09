VALID_PAYLOAD = {
    "distance_km": 850,
    "duree_h": 6.5,
    "type_train": "TGV inOui",
    "service_type": "Jour",
    "nom_operateur": "SNCF",
    "pays_origine": "FR",
    "pays_destination": "FR",
}


def test_predict_returns_a_plausible_frequency(client):
    resp = client.post("/predict", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["frequence_semaine_predite"] <= 7
    assert body["modele"] == "random_forest"


def test_predict_missing_field_returns_422(client):
    payload = dict(VALID_PAYLOAD)
    del payload["distance_km"]
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 422


def test_predict_is_deterministic(client):
    """Same input -> same output (model already trained, no random component at inference time)."""
    r1 = client.post("/predict", json=VALID_PAYLOAD).json()
    r2 = client.post("/predict", json=VALID_PAYLOAD).json()
    assert r1 == r2


def test_predict_night_train_differs_from_day_train(client):
    jour = client.post("/predict", json=VALID_PAYLOAD).json()["frequence_semaine_predite"]
    nuit_payload = dict(VALID_PAYLOAD, service_type="Nuit", type_train="Intercites de nuit", duree_h=13.0)
    nuit = client.post("/predict", json=nuit_payload).json()["frequence_semaine_predite"]
    assert jour != nuit
