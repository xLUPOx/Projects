"""I tool esposti al modello.

Sono funzioni Python normali: le docstring e le annotazioni di tipo sono cio'
che Gemini legge per costruire lo schema, quindi qui la docstring e' interfaccia,
non commento. Ogni tool restituisce dati grezzi con gli id degli alberi: sono
quelli che il frontend usa per evidenziare le feature sulla mappa e per rendere
cliccabile la citazione.
"""
from typing import Any

import cadastre
import rag


def search_trees(
    district: str | None = None,
    species: str | None = None,
    risk_classes: list[str] | None = None,
    health_status: str | None = None,
    protected_only: bool | None = None,
    inspection_older_than_months: int | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Cerca alberi nel catasto comunale filtrando per attributi.

    Args:
        district: Nome (anche parziale) del quartiere, es. 'Gries'.
        species: Nome scientifico o comune, es. 'Platanus' oppure 'platano'.
        risk_classes: Classi di propensione al cedimento da includere, es. ['C', 'D'].
        health_status: Uno tra 'Buono', 'Discreto', 'Scadente', 'Critico'.
        protected_only: Se True restituisce solo gli esemplari tutelati.
        inspection_older_than_months: Solo alberi la cui ultima ispezione risale
            ad almeno questo numero di mesi fa. Per 'da almeno 2 anni' usare 24.
        limit: Numero massimo di alberi restituiti (il conteggio totale e' sempre esatto).
    """
    return cadastre.search(
        district=district,
        species=species,
        risk_classes=risk_classes,
        health_status=health_status,
        protected_only=protected_only,
        inspection_older_than_months=inspection_older_than_months,
        limit=limit,
    )


def search_trees_near(
    place_name: str,
    radius_m: float = 200,
    risk_classes: list[str] | None = None,
    species: str | None = None,
    inspection_older_than_months: int | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Cerca alberi entro un raggio da un luogo di riferimento (scuola, parco, ospedale).

    Usare questo tool quando la domanda contiene una relazione spaziale del tipo
    'vicino a', 'entro N metri da', 'attorno a'.

    Args:
        place_name: Nome del luogo, es. 'Scuola Primaria Gries'.
        radius_m: Raggio di ricerca in metri.
        risk_classes: Classi di rischio da includere, es. ['C', 'D'].
        species: Nome scientifico o comune della specie.
        inspection_older_than_months: Solo alberi non ispezionati da almeno tanti mesi.
        limit: Numero massimo di alberi restituiti.
    """
    return cadastre.search_near(
        place_name=place_name,
        radius_m=radius_m,
        risk_classes=risk_classes,
        species=species,
        inspection_older_than_months=inspection_older_than_months,
        limit=limit,
    )


def cadastre_stats(
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
    """Conta gli alberi raggruppandoli per un campo, con gli stessi filtri di search_trees.

    Usare per ogni domanda che chiede una ripartizione, una distribuzione o un
    grafico. L'interfaccia disegna da sola il grafico a barre con questi dati:
    non serve descriverlo a parole ne' disegnarlo nel testo.

    Args:
        group_by: Uno tra 'risk_class', 'district', 'species',
            'common_name', 'health_status'.
        district: Limita il conteggio a un quartiere.
        species: Limita a una specie (nome scientifico o comune).
        risk_classes: Limita ad alcune classi, es. ['C', 'D'].
        health_status: Uno tra 'Buono', 'Discreto', 'Scadente', 'Critico'.
        protected_only: Se True conta solo gli esemplari tutelati.
        inspection_older_than_months: Solo alberi non ispezionati da almeno tanti mesi.
        place_name: Limita il conteggio agli alberi vicini a un luogo di
            riferimento. Da usare sempre quando si vuole il grafico di un
            risultato spaziale, cosi' che il grafico conti gli stessi alberi
            elencati nel testo e non un insieme piu' ampio.
        radius_m: Raggio in metri attorno a place_name.
    """
    return cadastre.stats(
        group_by=group_by,
        district=district,
        species=species,
        risk_classes=risk_classes,
        health_status=health_status,
        protected_only=protected_only,
        inspection_older_than_months=inspection_older_than_months,
        place_name=place_name,
        radius_m=radius_m,
    )


def consult_regulation(question: str) -> dict[str, Any]:
    """Cerca nel regolamento comunale del verde gli articoli utili a rispondere.

    Usare per domande su norme, obblighi, frequenze di potatura o di ispezione,
    abbattimenti, distanze dai cantieri, tempi di presa in carico delle segnalazioni.

    Args:
        question: La domanda dell'utente, riformulata in modo autosufficiente.
    """
    return rag.search(question)


def allowed_values() -> dict[str, Any]:
    """Elenca quartieri, specie, classi di rischio e luoghi realmente presenti nei dati.

    Usare prima di filtrare se non si e' certi che un nome esista, cosi' da non
    inventare valori.
    """
    return cadastre.registry()


TOOLS = {
    "search_trees": search_trees,
    "search_trees_near": search_trees_near,
    "cadastre_stats": cadastre_stats,
    "consult_regulation": consult_regulation,
    "allowed_values": allowed_values,
}

# Etichette mostrate nella chat mentre il tool sta girando.
LABELS = {
    "search_trees": "Interrogo il catasto alberi",
    "search_trees_near": "Eseguo una query spaziale sul catasto",
    "cadastre_stats": "Calcolo le statistiche del catasto",
    "consult_regulation": "Consulto il regolamento del verde",
    "allowed_values": "Verifico i valori disponibili nei dati",
}
