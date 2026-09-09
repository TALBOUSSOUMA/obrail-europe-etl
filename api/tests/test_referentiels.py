def test_list_pays(client):
    resp = client.get("/pays")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 26
    assert {"code_pays", "nom_pays"} <= set(body[0].keys())


def test_list_operateurs(client):
    resp = client.get("/operateurs")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_list_gares(client):
    """Feeds the frontend's autocomplete (<datalist>) for the
    departure/arrival city filters - see DessertesPage.jsx."""
    resp = client.get("/gares")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert {"nom_gare", "code_pays"} <= set(body[0].keys())


def test_list_types_train(client):
    """Feeds the frontend's 'Type de train' dropdown."""
    resp = client.get("/types-train")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    noms = {t["type_train"] for t in body}
    assert "TGV inOui" in noms
    # No duplicates: each value must appear only once.
    assert len(noms) == len(body)


def test_quality_log_has_entries(client):
    resp = client.get("/qualite?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert body[0]["taux_completude_pct"] >= 0


def test_stats_operateurs_sum_matches_total_dessertes(client):
    total_dessertes = client.get("/dessertes?limit=1").json()["total"]
    stats = client.get("/stats/operateurs").json()
    somme = sum(row["nb_dessertes"] for row in stats)
    assert somme == total_dessertes


def test_stats_pays_sum_matches_total_dessertes(client):
    total_dessertes = client.get("/dessertes?limit=1").json()["total"]
    stats = client.get("/stats/pays").json()
    somme = sum(row["nb_dessertes"] for row in stats)
    assert somme == total_dessertes
