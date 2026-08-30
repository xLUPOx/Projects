"""Genera il catasto alberi finto (GeoJSON) usato come sorgente dati della demo.

    python seed_data.py                              # come la demo
    python seed_data.py --seed 42 --epoca 2027-01-15

L'output e' deterministico: stessi parametri, stesso file. Sono due parametri e
non uno solo perche' governano cose diverse, e conviene poterli muovere
separatamente:

    seed   quali alberi escono (specie, quartiere, classe, stato)
    epoca  rispetto a quando sono datate le ispezioni

Finiscono entrambi dentro il GeoJSON: il dato dichiara come e' stato prodotto, e
`cadastre.reference_date()` rilegge l'epoca invece di usare `date.today()`.

Cambiando il seed cambiano i tre conteggi raccolti in `DEMO_FACTS`, in cima a
test_cadastre.py: vanno riscritti li' a mano. Sono pochi apposta.
"""
import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SEED = 20260826
DEFAULT_EPOCH = date(2026, 8, 26)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Riassegnata da main(): le funzioni di generazione la leggono come "oggi".
TODAY = DEFAULT_EPOCH

# Quartieri di Bolzano: centroide approssimativo e raggio di dispersione in gradi.
#
# Il raggio conta piu' di quanto sembri. Nella prima stesura era 0.010-0.012 di
# latitudine, cioe' oltre un chilometro in ogni direzione: con centroidi distanti
# uno o due chilometri, le cinque nuvole si sovrapponevano quasi del tutto e un
# albero etichettato "Gries" finiva disegnato sopra un altro quartiere. La query
# restava giusta — il quartiere e' un attributo del catasto, non si deduce dal
# punto — ma sulla mappa la risposta sembrava sbagliata.
#
# 0.005 di latitudine sono circa 550 m: le nuvole restano separate e
# l'etichetta corrisponde a quello che si vede.
DISTRICTS = {
    "Centro-Piani-Rencio": (46.4990, 11.3565, 0.0050),
    "Gries-San Quirino": (46.5045, 11.3285, 0.0050),
    "Oltrisarco-Aslago": (46.4818, 11.3700, 0.0050),
    "Europa-Novacella": (46.4868, 11.3255, 0.0042),
    "Don Bosco": (46.4902, 11.3025, 0.0050),
}

# nome scientifico -> (nome comune, intervallo di potatura in mesi)
SPECIES = {
    "Platanus x acerifolia": ("Platano", 36),
    "Tilia cordata": ("Tiglio", 48),
    "Acer platanoides": ("Acero riccio", 48),
    "Aesculus hippocastanum": ("Ippocastano", 36),
    "Celtis australis": ("Bagolaro", 60),
    "Quercus robur": ("Farnia", 60),
    "Pinus nigra": ("Pino nero", 84),
    "Fraxinus excelsior": ("Frassino", 48),
}

RISK_CLASSES = ["A", "B", "C", "D"]
RISK_WEIGHTS = [0.45, 0.30, 0.18, 0.07]

HEALTH_STATUSES = ["Buono", "Discreto", "Scadente", "Critico"]
HEALTH_WEIGHTS = [0.5, 0.3, 0.15, 0.05]

# Punti di interesse: servono alle query spaziali ("entro 200 m da...")
# Ogni luogo sta dentro la nuvola di alberi del suo quartiere: se cade fuori,
# le query spaziali restituiscono zero e la demo non mostra nulla.
PLACES = [
    {"name": "Scuola Primaria Gries", "type": "scuola", "lat": 46.5042, "lng": 11.3292},
    {"name": "Scuola Media Archimede", "type": "scuola", "lat": 46.4900, "lng": 11.3032},
    {"name": "Ospedale di Bolzano", "type": "ospedale", "lat": 46.4872, "lng": 11.3262},
    {"name": "Parco Petrarca", "type": "parco", "lat": 46.4988, "lng": 11.3558},
    {"name": "Stazione di Bolzano", "type": "stazione", "lat": 46.4975, "lng": 11.3600},
    {"name": "Asilo Firmian", "type": "scuola", "lat": 46.4820, "lng": 11.3705},
]


def _random_date(min_years: float, max_years: float) -> date:
    days = random.randint(int(min_years * 365), int(max_years * 365))
    return TODAY - timedelta(days=days)


def generate_trees(quantity: int = 140) -> list[dict]:
    trees = []
    for i in range(1, quantity + 1):
        district = random.choice(list(DISTRICTS))
        lat0, lng0, spread = DISTRICTS[district]
        lat = round(lat0 + random.uniform(-spread, spread), 6)
        lng = round(lng0 + random.uniform(-spread, spread) * 1.4, 6)

        species = random.choice(list(SPECIES))
        common_name, pruning_interval = SPECIES[species]
        risk_class = random.choices(RISK_CLASSES, RISK_WEIGHTS)[0]

        # Gli alberi piu' a rischio tendono ad avere ispezioni piu' vecchie:
        # e' quello che rende interessante la query "rischio alto + non ispezionati".
        if risk_class in ("C", "D"):
            last_inspection = _random_date(0.5, 4.0)
        else:
            last_inspection = _random_date(0.1, 2.5)

        trees.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "id": f"ALB-{i:04d}",
                "species": species,
                "common_name": common_name,
                "district": district,
                "street": f"Via Demo {random.randint(1, 60)}",
                "planting_date": _random_date(3, 80).isoformat(),
                "height_m": round(random.uniform(3.5, 24.0), 1),
                "girth_cm": random.randint(35, 320),
                "risk_class": risk_class,
                "health_status": random.choices(HEALTH_STATUSES, HEALTH_WEIGHTS)[0],
                "last_inspection": last_inspection.isoformat(),
                "last_pruning": _random_date(0.2, 7.0).isoformat(),
                "pruning_interval_months": pruning_interval,
                "protected": random.random() < 0.08,
            },
        })
    return trees


def main(seed: int = DEFAULT_SEED, epoch: date = DEFAULT_EPOCH) -> None:
    global TODAY
    TODAY = epoch
    random.seed(seed)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # I due parametri viaggiano nel dato. `generated_on` in particolare non e'
    # decorazione: e' la data rispetto a cui sono state calcolate le ispezioni,
    # e il catasto la rilegge come "oggi", cosi' "non ispezionati da 24 mesi"
    # resta lo stesso insieme fra sei mesi. Senza, il dato e' fermo al seed ma i
    # mesi trascorsi scorrono col calendario e i conteggi scadono da soli.
    geojson = {
        "type": "FeatureCollection",
        "seed": seed,
        "generated_on": TODAY.isoformat(),
        "features": generate_trees(),
    }
    (DATA_DIR / "trees.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (DATA_DIR / "places.json").write_text(
        json.dumps(PLACES, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"Scritti {len(geojson['features'])} alberi e {len(PLACES)} luoghi in {DATA_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"quali alberi escono (default {DEFAULT_SEED})")
    parser.add_argument("--epoca", type=date.fromisoformat, default=DEFAULT_EPOCH,
                        metavar="AAAA-MM-GG",
                        help=f"data rispetto a cui datare le ispezioni (default {DEFAULT_EPOCH})")
    arguments = parser.parse_args()
    main(seed=arguments.seed, epoch=arguments.epoca)
