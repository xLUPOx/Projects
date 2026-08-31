"""Smoke test degli endpoint. Offline: nessuna chiamata al modello.

Serve soprattutto a coprire il ciclo di vita dell'app. Il caricamento di
catasto e regolamento avviene nel `lifespan` di FastAPI, e una migrazione
sbagliata li' non rompe nessun import: rompe solo il server, in esecuzione.
`TestClient` usato come context manager esegue davvero lifespan.
"""
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

# I test stanno in backend/tests/, i moduli in backend/: senza questo
# `import cadastre` non risolve. Stesso accorgimento di eval/run.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # importa per primo: e' lui a caricare .env

# Il lifespan inizializza anche il RAG, che con la chiave in .env indicizza il
# regolamento con gli embedding: cinque chiamate di rete per un test che si
# dichiara offline. Senza chiave indicizza con BM25 e il ciclo di vita — che e'
# cio' che questo file verifica — resta esattamente lo stesso.
# keys.py legge prima GEMINI_API_KEYS: vanno tolte entrambe, altrimenti
# con un pool in .env questo test "offline" chiamerebbe la rete.
for _var in ("GEMINI_API_KEYS", "GEMINI_API_KEY"):
    os.environ.pop(_var, None)


def test_lifespan_loads_the_data():
    with TestClient(main.app) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["trees_loaded"] == 140
    assert body["rag"] != "non inizializzato"


def test_read_endpoints():
    with TestClient(main.app) as client:
        cadastre = client.get("/api/cadastre").json()
        places = client.get("/api/places").json()
        registry = client.get("/api/registry").json()
    assert cadastre["type"] == "FeatureCollection"
    assert len(cadastre["features"]) == 140
    assert len(places) == 6
    assert len(registry["districts"]) == 5

    # Le proprieta' del GeoJSON sono il contratto con l'interfaccia Tree di
    # types.ts: e' l'unico confine che ne' i test ne' il compilatore Angular
    # possono controllare da soli. Un campo rinominato qui non rompe niente,
    # esce solo come "undefined" nel popup della mappa.
    props = cadastre["features"][0]["properties"]
    for field in (
        "id", "species", "common_name", "district", "street", "risk_class",
        "health_status", "last_inspection", "months_since_inspection",
        "height_m", "protected", "lat", "lng",
    ):
        assert field in props, field


def test_startup_is_still_callable_on_its_own():
    """`eval/run.py` gira senza server e chiama `main.startup()` direttamente:
    deve restare una funzione normale, non solo un pezzo del lifespan."""
    main.startup()
    assert main.cadastre.registry()["total_trees"] == 140


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
