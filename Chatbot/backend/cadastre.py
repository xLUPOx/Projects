"""Accesso ai dati del catasto alberi.

Il GeoJSON generato da seed_data.py viene caricato in un SQLite in memoria
all'avvio. Le query attributive le fa SQL, quelle spaziali le fa una haversine
in Python dopo un prefiltro a bounding box: in produzione questo strato
diventerebbe PostGIS (ST_DWithin) senza toccare la firma delle funzioni.
"""
import difflib
import json
import math
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from dateutil.relativedelta import relativedelta
from geographiclib.geodesic import Geodesic

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Lunghezza del grado di latitudine al suo *minimo* (equatore). Serve al
# prefiltro a bounding box, che ha un solo invariante: non deve mai escludere
# un albero che la distanza esatta accetterebbe. Con 111_320 (il valore medio)
# il riquadro risultava piu' stretto del raggio richiesto e un albero a 399,5 m
# spariva prima che la haversine lo vedesse.
MIN_METERS_PER_LAT_DEGREE = 110_574

_conn: sqlite3.Connection | None = None
_places: list[dict[str, Any]] = []
_generated_on: date | None = None

# Le date restano TEXT di proposito: in formato ISO si ordinano e si
# confrontano lessicograficamente, che e' esattamente quello che serve a
# `last_inspection < ?`. Il resto ha il suo tipo, cosi' i valori tornano gia'
# numerici da sqlite3 e non serve riconvertirli a mano dopo ogni SELECT.
FIELDS = {
    "id": "TEXT",
    "species": "TEXT",
    "common_name": "TEXT",
    "district": "TEXT",
    "street": "TEXT",
    "planting_date": "TEXT",
    "height_m": "REAL",
    "girth_cm": "INTEGER",
    "risk_class": "TEXT",
    "health_status": "TEXT",
    "last_inspection": "TEXT",
    "last_pruning": "TEXT",
    "pruning_interval_months": "INTEGER",
    "protected": "INTEGER",
}


def initialize() -> None:
    """Carica GeoJSON e luoghi in memoria. Idempotente."""
    global _conn, _places
    if _conn is not None:
        return

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    columns = ", ".join(f"{name} {kind}" for name, kind in FIELDS.items())
    conn.execute(f"CREATE TABLE trees ({columns}, lat REAL, lng REAL)")

    geojson = json.loads((DATA_DIR / "trees.geojson").read_text(encoding="utf-8"))
    global _generated_on
    stamp = geojson.get("generated_on")
    _generated_on = date.fromisoformat(stamp) if stamp else None
    rows = []
    for feature in geojson["features"]:
        p = feature["properties"]
        lng, lat = feature["geometry"]["coordinates"]
        rows.append([p[c] for c in FIELDS] + [lat, lng])

    placeholders = ", ".join("?" * (len(FIELDS) + 2))
    conn.executemany(f"INSERT INTO trees VALUES ({placeholders})", rows)
    conn.commit()

    _conn = conn
    _places = json.loads((DATA_DIR / "places.json").read_text(encoding="utf-8"))


def _db() -> sqlite3.Connection:
    if _conn is None:
        initialize()
    assert _conn is not None
    return _conn


def places() -> list[dict[str, Any]]:
    if not _places:
        initialize()
    return _places


def reference_date() -> date:
    """L'"oggi" del catasto: la data in cui i dati sono stati generati.

    Le ispezioni sono state distribuite all'indietro a partire da quella data.
    Misurare i mesi trascorsi con `date.today()` faceva scorrere l'insieme
    "non ispezionati da 24 mesi" con il calendario, mentre il dato restava
    fermo: gli stessi conteggi cambiavano da soli col passare dei mesi e le
    asserzioni dei test scadevano senza che nessuno avesse toccato niente.
    Con un catasto reale, dove le ispezioni si aggiornano, questa funzione
    torna a essere `date.today()` — e' il dato finto a dover dichiarare la
    propria epoca, non il codice a doverla indovinare.
    """
    initialize()
    return _generated_on or date.today()


def _months_elapsed(iso_date: str) -> int:
    """Mesi interi trascorsi da una data. `relativedelta` tiene conto del
    giorno: fra il 31 gennaio e il 1 febbraio e' passato 0, non 1."""
    delta = relativedelta(reference_date(), date.fromisoformat(iso_date))
    return delta.years * 12 + delta.months


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["protected"] = bool(d["protected"])
    d["months_since_inspection"] = _months_elapsed(d["last_inspection"])
    d["months_since_pruning"] = _months_elapsed(d["last_pruning"])
    return d


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distanza geodetica in metri sull'ellissoide WGS-84.

    La calcola `geographiclib`, l'implementazione di riferimento di Karney: la
    stessa matematica che PROJ porta dentro PostGIS, quindi passare a
    `ST_Distance` non cambierebbe il numero. La haversine che stava qui prima
    trattava la Terra come una sfera e sbagliava fino a mezzo punto percentuale;
    su un catasto la distanza e' un dato, non una stima, e la libreria toglie
    l'approssimazione senza aggiungere codice da mantenere.
    """
    return Geodesic.WGS84.Inverse(lat1, lng1, lat2, lng2)["s12"]


def _degree_deltas(lat: float, radius_m: float) -> tuple[float, float]:
    """Semiampiezze in gradi del bounding box che contiene il cerchio di raggio
    dato. Deve sempre eccedere il raggio, mai stringerlo: chi lo attraversa
    viene poi filtrato da `distance_m`, chi ne resta fuori non viene piu' visto."""
    return (
        radius_m / MIN_METERS_PER_LAT_DEGREE,
        radius_m / (MIN_METERS_PER_LAT_DEGREE * math.cos(math.radians(lat))),
    )


def _cutoff_date(months: int) -> str:
    """Data ISO di 'months' mesi fa: soglia per i confronti sulle ispezioni.

    `relativedelta` risolve da solo i mesi corti: il 31 maggio meno un mese e'
    il 30 aprile. Farlo a mano obbligava a troncare il giorno a 28 per non
    costruire un 31 febbraio, e la soglia usciva sbagliata di qualche giorno.
    """
    return (reference_date() - relativedelta(months=months)).isoformat()


def _where_clauses(
    district: str | None,
    species: str | None,
    risk_classes: list[str] | None,
    health_status: str | None,
    protected_only: bool | None,
    inspection_older_than_months: int | None,
) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    values: list[Any] = []

    if district:
        where.append("LOWER(district) LIKE ?")
        values.append(f"%{district.lower()}%")
    if species:
        # accetta sia il nome scientifico sia quello comune
        where.append("(LOWER(species) LIKE ? OR LOWER(common_name) LIKE ?)")
        values.extend([f"%{species.lower()}%", f"%{species.lower()}%"])
    if risk_classes:
        placeholders = ", ".join("?" * len(risk_classes))
        where.append(f"risk_class IN ({placeholders})")
        values.extend([c.upper() for c in risk_classes])
    if health_status:
        where.append("LOWER(health_status) = ?")
        values.append(health_status.lower())
    if protected_only:
        where.append("protected = 1")
    if inspection_older_than_months is not None:
        # confronto lessicografico: le date ISO si ordinano come stringhe
        where.append("last_inspection < ?")
        values.append(_cutoff_date(inspection_older_than_months))

    return where, values


def search(
    district: str | None = None,
    species: str | None = None,
    risk_classes: list[str] | None = None,
    health_status: str | None = None,
    protected_only: bool | None = None,
    inspection_older_than_months: int | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    where, values = _where_clauses(
        district, species, risk_classes, health_status,
        protected_only, inspection_older_than_months,
    )
    filter_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total = _db().execute(
        "SELECT COUNT(*) AS n FROM trees" + filter_sql, values
    ).fetchone()["n"]

    rows = _db().execute(
        "SELECT * FROM trees" + filter_sql
        + " ORDER BY risk_class DESC, last_inspection ASC LIMIT ?",
        values + [limit],
    ).fetchall()

    return {
        "total_matching": total,
        "returned": len(rows),
        "trees": [_row_to_dict(r) for r in rows],
    }


def _find_place(name: str) -> dict[str, Any] | None:
    """Tre stadi, dal piu' stretto al piu' permissivo.

    Il fuzzy va per ultimo apposta: su una query corta come "Gries" il punteggio
    di similarita' contro "Scuola Primaria Gries" e' basso, e anteporlo farebbe
    perdere un caso che oggi funziona. E la soglia resta alta, perche' "Piazza
    Che Non Esiste" deve continuare a non somigliare a nulla: l'errore parlante
    che ne segue e' cio' che permette al modello di correggersi.
    """
    normalized = name.lower().strip()
    names = [place["name"].lower() for place in places()]

    for place, place_name in zip(places(), names):
        if normalized in place_name:
            return place

    words = [w for w in normalized.split() if len(w) > 3]
    for place, place_name in zip(places(), names):
        if any(w in place_name for w in words):
            return place

    # Ultimo stadio: refusi ("Scuola Primara Gris").
    close = difflib.get_close_matches(normalized, names, n=1, cutoff=0.6)
    if close:
        return places()[names.index(close[0])]
    return None


def search_near(
    place_name: str,
    radius_m: float = 200,
    risk_classes: list[str] | None = None,
    species: str | None = None,
    inspection_older_than_months: int | None = None,
    limit: int = 25,
    district: str | None = None,
    health_status: str | None = None,
    protected_only: bool | None = None,
) -> dict[str, Any]:
    place = _find_place(place_name)
    if place is None:
        # Errore parlante: il modello puo' riproporre la domanda con un luogo valido.
        return {
            "error": f"Luogo '{place_name}' non presente nell'anagrafica.",
            "available_places": [x["name"] for x in places()],
        }

    where, values = _where_clauses(
        district, species, risk_classes, health_status,
        protected_only, inspection_older_than_months,
    )
    # Prefiltro a bounding box: evita la haversine su tutto il catasto.
    delta_lat, delta_lng = _degree_deltas(place["lat"], radius_m)
    where += ["lat BETWEEN ? AND ?", "lng BETWEEN ? AND ?"]
    values += [
        place["lat"] - delta_lat, place["lat"] + delta_lat,
        place["lng"] - delta_lng, place["lng"] + delta_lng,
    ]

    candidates = _db().execute(
        "SELECT * FROM trees WHERE " + " AND ".join(where), values
    ).fetchall()

    inside = []
    for row in candidates:
        d = distance_m(place["lat"], place["lng"], row["lat"], row["lng"])
        if d <= radius_m:
            tree = _row_to_dict(row)
            tree["distance_m"] = round(d)
            inside.append(tree)

    inside.sort(key=lambda t: t["distance_m"])
    return {
        "place": place,
        "radius_m": radius_m,
        "total_matching": len(inside),
        "returned": min(len(inside), limit),
        "trees": inside[:limit],
    }


GROUPABLE_FIELDS = {
    "risk_class", "district", "species", "common_name", "health_status",
}


def stats(
    group_by: str,
    district: str | None = None,
    species: str | None = None,
    risk_classes: list[str] | None = None,
    health_status: str | None = None,
    protected_only: bool | None = None,
    inspection_older_than_months: int | None = None,
    place_name: str | None = None,
    radius_m: float | None = None,
) -> dict[str, Any]:
    """Conta gli alberi per categoria, sullo stesso sottoinsieme che sanno
    filtrare `search` e `search_near` — vincolo spaziale compreso.

    Il raggio serve piu' di quanto sembri: senza, "grafica gli alberi a rischio
    entro 400 m dalla scuola" non e' esprimibile, e il grafico finisce per
    contare il quartiere intero mentre il testo parla di tre alberi. Due numeri
    diversi nella stessa risposta, entrambi giusti: il modo piu' rapido di far
    perdere fiducia a chi legge.
    """
    if group_by not in GROUPABLE_FIELDS:
        return {
            "error": f"Campo '{group_by}' non raggruppabile.",
            "valid_fields": sorted(GROUPABLE_FIELDS),
        }

    if place_name:
        # Tutti i filtri, non solo quelli che `search_near` accettava prima:
        # quartiere, stato fitosanitario e tutela finivano comunque nel
        # sottotitolo del grafico senza essere applicati al conteggio, ed e'
        # esattamente la divergenza che questa funzione esiste per impedire.
        near = search_near(
            place_name=place_name,
            radius_m=radius_m or 200,
            risk_classes=risk_classes,
            species=species,
            inspection_older_than_months=inspection_older_than_months,
            limit=10_000,
            district=district,
            health_status=health_status,
            protected_only=protected_only,
        )
        if "error" in near:
            return near
        counts = Counter(t[group_by] for t in near["trees"])
        rows = [
            {"key": key, "count": n}
            for key, n in counts.most_common()
        ]
        total = near["total_matching"]
        counted = near["trees"]
    else:
        where, values = _where_clauses(
            district, species, risk_classes, health_status,
            protected_only, inspection_older_than_months,
        )
        filter_sql = (" WHERE " + " AND ".join(where)) if where else ""
        result = _db().execute(
            f"SELECT {group_by} AS key, COUNT(*) AS n FROM trees"
            + filter_sql
            + " GROUP BY key ORDER BY n DESC",
            values,
        ).fetchall()
        rows = [{"key": r["key"], "count": r["n"]} for r in result]
        total = sum(r["count"] for r in rows)
        # Gli stessi alberi che le barre contano, non i primi venticinque:
        # servono ad accendere in mappa cio' che il grafico riassume, e un
        # grafico che dice 26 sopra una mappa che ne illumina 25 e' peggio di
        # una mappa spenta.
        counted = [
            _row_to_dict(r)
            for r in _db().execute(
                "SELECT * FROM trees" + filter_sql, values
            ).fetchall()
        ]

    return {
        "group_by": group_by,
        "filters": _describe_filters(
            district, species, risk_classes, health_status,
            protected_only, inspection_older_than_months,
            place_name, radius_m,
        ),
        "total": total,
        "counts": rows,
        # Il grafico e' un'affermazione su alberi precisi: qui ci sono, cosi'
        # la mappa mostra l'insieme di cui le barre sono il riassunto. Il testo
        # non li nomina uno per uno, quindi non diventano targhette: la
        # citazione puntuale e l'evidenziazione d'insieme sono due cose diverse.
        "trees": counted,
    }


def _describe_filters(
    district: str | None,
    species: str | None,
    risk_classes: list[str] | None,
    health_status: str | None,
    protected_only: bool | None,
    inspection_older_than_months: int | None,
    place_name: str | None = None,
    radius_m: float | None = None,
) -> str:
    """Frase leggibile per il titolo del grafico: dice su cosa e' stato contato."""
    parts = []
    if species:
        parts.append(species)
    if district:
        parts.append(f"a {district}")
    if risk_classes:
        parts.append("classe " + "/".join(c.upper() for c in risk_classes))
    if health_status:
        parts.append(f"stato {health_status}")
    if protected_only:
        parts.append("solo tutelati")
    if inspection_older_than_months:
        parts.append(f"non ispezionati da {inspection_older_than_months} mesi")
    if place_name:
        parts.append(f"entro {radius_m or 200:.0f} m da {place_name}")
    return " · ".join(parts)


def registry() -> dict[str, Any]:
    """Valori ammessi: serve al modello per non inventare quartieri o specie."""
    districts = [
        r["district"]
        for r in _db().execute("SELECT DISTINCT district FROM trees ORDER BY district")
    ]
    species = [
        {"scientific": r["species"], "common": r["common_name"]}
        for r in _db().execute(
            "SELECT DISTINCT species, common_name FROM trees ORDER BY common_name"
        )
    ]
    return {
        "districts": districts,
        "species": species,
        "risk_classes": ["A", "B", "C", "D"],
        "health_statuses": [
            r["health_status"]
            for r in _db().execute(
                "SELECT DISTINCT health_status FROM trees ORDER BY health_status"
            )
        ],
        "landmarks": [
            {"name": x["name"], "type": x["type"]} for x in places()
        ],
        "total_trees": _db().execute("SELECT COUNT(*) AS n FROM trees").fetchone()["n"],
    }


def all_geojson() -> dict[str, Any]:
    """Il catasto completo, per il primo rendering della mappa."""
    rows = _db().execute("SELECT * FROM trees").fetchall()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["lng"], r["lat"]]},
                "properties": _row_to_dict(r),
            }
            for r in rows
        ],
    }
