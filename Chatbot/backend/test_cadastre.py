"""Smoke test dello strato dati: gira senza API key, senza rete, senza server.

    python test_cadastre.py
"""
import json
from pathlib import Path

import cadastre

# I soli numeri che dipendono davvero dal seed della generazione. Tutto il
# resto — 140 alberi, 5 quartieri, 6 luoghi — sono parametri del generatore
# (`quantity`, `DISTRICTS`, `PLACES`) e restano identici estraendo un'altra
# volta: cambiare seed non li tocca.
#
# Vanno riscritti a mano, guardando i dati, quando si cambia `--seed` o
# `--epoca` in seed_data.py. Non li genera il seeder di proposito: se li
# scrivesse lui, l'asserzione confronterebbe il generatore con se' stesso e non
# verificherebbe piu' niente. Sono tre apposta, e questo e' l'unico posto in cui
# stanno scritti — test_agent.py e la suite eval li rileggono da qui.
DEMO_FACTS = {
    "epoca": "2026-08-26",
    "tigli_a_gries": 6,
    "classe_d_da_24_mesi": 4,
}


def test_registry_is_consistent():
    r = cadastre.registry()
    assert r["total_trees"] == 140
    assert len(r["districts"]) == 5
    assert len(r["landmarks"]) == 6


def test_attribute_filter():
    r = cadastre.search(risk_classes=["D"])
    assert r["total_matching"] > 0
    assert all(t["risk_class"] == "D" for t in r["trees"])


def test_species_filter_matches_common_name():
    r = cadastre.search(species="tiglio", limit=5)
    assert all("Tilia" in t["species"] for t in r["trees"])


def test_overdue_inspection_filter():
    r = cadastre.search(inspection_older_than_months=24, limit=100)
    assert all(t["months_since_inspection"] >= 24 for t in r["trees"])


def test_limit_does_not_skew_the_total():
    r = cadastre.search(limit=3)
    assert r["returned"] == 3
    assert r["total_matching"] == 140


def test_spatial_query():
    r = cadastre.search_near("Scuola Primaria Gries", radius_m=300)
    assert "error" not in r
    assert all(t["distance_m"] <= 300 for t in r["trees"])
    # ordinati per distanza crescente
    distances = [t["distance_m"] for t in r["trees"]]
    assert distances == sorted(distances)


def test_protected_only():
    r = cadastre.search(protected_only=True, limit=100)
    assert r["total_matching"] > 0
    assert all(t["protected"] is True for t in r["trees"])


def test_place_name_with_typo():
    """Chi scrive la domanda sbaglia i nomi. Il fuzzy e' l'ultimo stadio di
    _find_place e serve a non far fallire la query per una lettera."""
    r = cadastre.search_near("Scuola Primara Gris", radius_m=300)
    assert "error" not in r, r.get("error")
    assert r["place"]["name"] == "Scuola Primaria Gries"


def test_bounding_box_contains_the_circle():
    """Il riquadro e' solo un'ottimizzazione: deve eccedere il raggio in ogni
    direzione, altrimenti un albero al bordo sparisce prima che la distanza
    esatta lo veda. Con 111_320 (grado medio) il lato nord-sud usciva piu'
    stretto del raggio richiesto.

    Il controllo e' sulla geometria, non sui 140 alberi generati: nessun albero
    cade per forza nella fascia da mezzo metro che la costante sbagliata perdeva.
    """
    for lat in (0.0, 46.5, 60.0):
        for radius in (100, 400, 2_000):
            d_lat, d_lng = cadastre._degree_deltas(lat, radius)
            north = cadastre.distance_m(lat, 11.0, lat + d_lat, 11.0)
            east = cadastre.distance_m(lat, 11.0, lat, 11.0 + d_lng)
            assert north >= radius, f"lat {lat}, raggio {radius}: bordo nord a {north:.1f} m"
            assert east >= radius, f"lat {lat}, raggio {radius}: bordo est a {east:.1f} m"


def test_prefilter_agrees_with_brute_force():
    """E il riquadro, per quanto largo, non deve nemmeno aggiungere falsi
    positivi: dopo il prefiltro il taglio esatto lo fa la haversine."""
    for place in cadastre.places():
        radius = 400
        via_prefilter = {
            t["id"]
            for t in cadastre.search_near(place["name"], radius_m=radius, limit=10_000)["trees"]
        }
        brute_force = {
            t["id"]
            for t in cadastre.search(limit=10_000)["trees"]
            if cadastre.distance_m(place["lat"], place["lng"], t["lat"], t["lng"]) <= radius
        }
        assert via_prefilter == brute_force, place["name"]


def test_inspection_threshold_agrees_both_ways():
    """`inspection_older_than_months` filtra in SQL con una data limite, ma i
    mesi mostrati all'utente li calcola Python: se le due strade non concordano,
    la lista contraddice la colonna che le sta accanto."""
    months = 24
    filtered = {t["id"] for t in cadastre.search(inspection_older_than_months=months, limit=10_000)["trees"]}
    expected = {t["id"] for t in cadastre.search(limit=10_000)["trees"] if t["months_since_inspection"] >= months}
    assert filtered == expected


def test_unknown_place_does_not_blow_up():
    r = cadastre.search_near("Piazza Che Non Esiste")
    assert "error" in r
    assert r["available_places"]


def test_stats_sum_to_the_total():
    s = cadastre.stats("risk_class")
    assert sum(c["count"] for c in s["counts"]) == 140


def test_stats_return_the_trees_they_counted():
    """Il grafico deve poter accendere in mappa cio' che riassume.

    `stats` tornava soli conteggi, quindi una domanda che chiedeva un grafico
    lasciava la mappa spenta: le barre dicevano 26 alberi e sullo schermo non
    se ne illuminava nessuno. Gli alberi restituiti devono essere tanti quanti
    le barre ne contano, in entrambi i rami — altrimenti la mappa contraddice
    il grafico che le sta accanto.
    """
    for kwargs in (
        {},
        {"district": "Centro-Piani-Rencio"},
        {"place_name": "Scuola Primaria Gries", "radius_m": 400},
    ):
        s = cadastre.stats("risk_class", **kwargs)
        assert len(s["trees"]) == s["total"], kwargs
        assert len(s["trees"]) == sum(c["count"] for c in s["counts"]), kwargs
        # e sono alberi veri, con un id: e' quello che la mappa evidenzia
        assert all(t["id"].startswith("ALB-") for t in s["trees"]), kwargs


def test_spatial_stats_count_what_the_subtitle_claims():
    """L'invariante di punta del progetto: il grafico conta lo stesso
    sottoinsieme che il testo elenca.

    Il ramo spaziale di `stats` passava a `search_near` solo tre filtri su sei —
    quartiere, stato fitosanitario e tutela cadevano — ma `_describe_filters` li
    scriveva lo stesso nel sottotitolo. Il grafico diceva "stato Buono, entro
    400 m" e contava tutti e 13 gli alberi del raggio, di cui Buono erano 4.
    Due numeri diversi nella stessa risposta, con l'etichetta a dare ragione a
    quello sbagliato.
    """
    place, radius = "Scuola Primaria Gries", 400

    plain = cadastre.stats("risk_class", place_name=place, radius_m=radius)
    near = cadastre.search_near(place, radius_m=radius, limit=10_000)
    assert plain["total"] == near["total_matching"]
    assert sum(c["count"] for c in plain["counts"]) == plain["total"]

    # e ogni filtro dichiarato nel sottotitolo deve restringere il conteggio
    for extra in (
        {"health_status": "Buono"},
        {"protected_only": True},
        {"risk_classes": ["C", "D"]},
        {"inspection_older_than_months": 24},
    ):
        filtered = cadastre.stats("risk_class", place_name=place, radius_m=radius, **extra)
        expected = cadastre.search_near(place, radius_m=radius, limit=10_000, **extra)
        assert filtered["total"] == expected["total_matching"], extra
        assert sum(c["count"] for c in filtered["counts"]) == filtered["total"], extra

    # un quartiere diverso da quello del luogo non puo' che dare zero
    other = cadastre.stats(
        "risk_class", place_name=place, radius_m=radius, district="Don Bosco"
    )
    assert other["total"] == 0


def test_the_demo_counts_are_the_ones_the_eval_expects():
    """I numeri che `eval/cases.json` si aspetta nella risposta del modello sono
    fatti sui dati generati. Se restano solo la', una modifica al seed li rompe
    nella suite che costa quota e che nessuno lancia per intero. Qui costano
    zero e falliscono subito."""
    assert (
        cadastre.search(district="Gries", species="tiglio", limit=100)["total_matching"]
        == DEMO_FACTS["tigli_a_gries"]
    )
    assert (
        cadastre.search(risk_classes=["D"], inspection_older_than_months=24, limit=100)[
            "total_matching"
        ]
        == DEMO_FACTS["classe_d_da_24_mesi"]
    )


def test_the_eval_expects_the_same_numbers_as_here():
    """`cases.json` e' un file di dati e non puo' importare DEMO_FACTS, quindi
    il legame lo tiene questo test: cambiando seed fallisce anche lui e dice
    quale riga del file va aggiornata. Senza, il conteggio sbagliato lo
    scopriresti otto minuti dopo, dentro la suite che consuma quota."""
    cases = json.loads(
        (Path(__file__).parent / "eval" / "cases.json").read_text(encoding="utf-8")
    )
    simple_count = next(c for c in cases if c["name"] == "simple_count")
    assert simple_count["must_contain"] == [str(DEMO_FACTS["tigli_a_gries"])]


def test_elapsed_months_do_not_drift_with_the_calendar():
    """I mesi trascorsi si misurano dalla data di generazione del catasto, non
    da oggi: e' cio' che tiene fermi i due conteggi qui sopra. Prima erano
    contati con `date.today()` e scivolavano da soli col passare dei mesi."""
    from datetime import date

    assert cadastre.reference_date() == date.fromisoformat(DEMO_FACTS["epoca"])
    tree = cadastre.search(limit=1)["trees"][0]
    expected = cadastre._months_elapsed(tree["last_inspection"])
    assert tree["months_since_inspection"] == expected

    # e la soglia SQL guarda la stessa data
    epoca = date.fromisoformat(DEMO_FACTS["epoca"])
    assert cadastre._cutoff_date(24) == epoca.replace(year=epoca.year - 2).isoformat()


def test_non_groupable_field():
    s = cadastre.stats("height_m")
    assert "error" in s


def test_geojson_is_valid():
    g = cadastre.all_geojson()
    assert g["type"] == "FeatureCollection"
    assert len(g["features"]) == 140
    assert g["features"][0]["geometry"]["type"] == "Point"


def test_the_demo_questions_return_results():
    """Guardia contro la trappola in cui siamo gia' caduti: una domanda di
    esempio che, con i dati generati, restituisce zero righe. La demo non deve
    mai mostrare una lista vuota per una domanda che promette risultati."""
    count = cadastre.search(district="Gries", species="tiglio", limit=50)
    assert count["total_matching"] > 0

    risk = cadastre.search(
        risk_classes=["D"], inspection_older_than_months=24, limit=50
    )
    assert risk["total_matching"] > 0

    spatial = cadastre.search_near(
        "Scuola Primaria Gries",
        radius_m=400,
        risk_classes=["C", "D"],
        inspection_older_than_months=24,
        limit=50,
    )
    assert spatial["total_matching"] > 0


def test_every_place_has_trees_nearby():
    """Un punto di riferimento fuori dalla nuvola di alberi del suo quartiere
    rende inutile qualunque query spaziale su di lui."""
    for place in cadastre.places():
        near = cadastre.search_near(place["name"], radius_m=300, limit=50)
        assert near["total_matching"] > 0, place["name"]


def test_districts_are_separate_on_the_map():
    """I quartieri devono essere nuvole distinte: se si sovrappongono, un albero
    etichettato 'Gries' appare sopra un altro quartiere e la risposta — pur
    corretta — sembra sbagliata."""
    centroids = {}
    for name in cadastre.registry()["districts"]:
        trees = cadastre.search(district=name, limit=200)["trees"]
        centroids[name] = (
            sum(t["lat"] for t in trees) / len(trees),
            sum(t["lng"] for t in trees) / len(trees),
        )

    names = list(centroids)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d = cadastre.distance_m(*centroids[a], *centroids[b])
            assert d > 1200, f"{a} e {b} distano solo {d:.0f} m"


if __name__ == "__main__":
    failed = 0
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            try:
                function()
                print(f"  ok   {name}")
            except AssertionError as e:
                failed += 1
                print(f"  FAIL {name}: {e}")
    print("tutti i test passati" if not failed else f"{failed} test falliti")
