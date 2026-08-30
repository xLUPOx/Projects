"""Il pool delle chiavi Gemini.

Il free tier concede pochissime richieste al minuto e un tetto giornaliero, e
una demo dal vivo ne consuma 2-3 per domanda: con una chiave sola la seconda
domanda del colloquio muore in diretta. Con piu' chiavi si cambia chiave invece
di aspettare — che e' gratis e istantaneo, mentre l'attesa non lo e'.

    GEMINI_API_KEYS=chiave1,chiave2,chiave3     (in alternativa a GEMINI_API_KEY)

**Le chiavi devono appartenere a progetti Google diversi.** Le quote del free
tier si contano per progetto, non per chiave: due chiavi dello stesso progetto
pescano dallo stesso secchio e la rotazione non compra niente.

Qui dentro ci sono solo i dati e le regole di scelta — nessun client, nessuna
rete — cosi' la logica di rotazione si prova offline (test_quota.py). Chi tiene
i client e' main.py, che ha una `genai.Client` per chiave.

I due limiti vanno trattati in modo opposto, ed e' tutto il punto del modulo:

    al minuto    torna buona in mezzo minuto: si aspetta
    giornaliero  non si aspetta mai, ma si riprova piu' tardi

Entrambi gli stop sono un istante di scadenza, non una bandierina: nessuno deve
riabilitare niente, le chiavi rientrano da sole quando il momento e' passato.
Cambia solo cosa se ne fa chi chiama: sulla pausa breve puo' dormire, sullo stop
lungo no — un utente davanti allo schermo non aspetta mezz'ora.
"""
import os
import time
from typing import Any

_keys: list[str] = []
_loaded = False

# Quanto sta fuori una chiave che ha finito la quota giornaliera, prima di
# essere riprovata. Le quote di Google si azzerano a mezzanotte del fuso
# Pacifico: calcolare quell'istante vorrebbe dire portarsi dietro un database
# dei fusi orari, mentre risondare ogni mezz'ora costa una richiesta rifiutata
# — che un 429 non consuma quota. Escluderla fino al riavvio, come faceva
# prima, lasciava fuori una chiave che Google aveva gia' riabilitato.
EXHAUSTED_RETRY_S = 1_800

# Entrambi sono chiave -> istante (time.monotonic) fino al quale non si usa.
# Restano separati perche' solo sul primo ha senso aspettare.
_paused: dict[str, float] = {}
_exhausted: dict[str, float] = {}


def load(raw: str | None = None) -> list[str]:
    """Legge le chiavi dall'ambiente, o dalla stringa passata (per i test).

    `GEMINI_API_KEYS` separate da virgola; se manca, la singola
    `GEMINI_API_KEY`, cosi' una configurazione esistente continua a funzionare
    senza toccare niente.
    """
    global _keys, _loaded, _exhausted, _paused
    if raw is None:
        raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""

    unique: list[str] = []
    for part in raw.split(","):
        key = part.strip()
        # Una chiave ripetuta e' peggio che inutile: darebbe l'illusione di un
        # margine che non c'e', visto che la quota e' la stessa.
        if key and key not in unique:
            unique.append(key)

    _keys, _loaded = unique, True
    _paused, _exhausted = {}, {}
    return list(_keys)


def all_keys() -> list[str]:
    if not _loaded:
        load()
    return list(_keys)


def _blocked(key: str, moment: float) -> bool:
    return _paused.get(key, 0.0) > moment or _exhausted.get(key, 0.0) > moment


def usable(now: float | None = None) -> str | None:
    """La prima chiave utilizzabile adesso, o None se non ce ne sono."""
    moment = time.monotonic() if now is None else now
    for key in all_keys():
        if not _blocked(key, moment):
            return key
    return None


def wait_time(now: float | None = None) -> float | None:
    """Secondi da aspettare perche' una chiave torni libera.

    None significa che aspettare non serve: o c'e' gia' una chiave libera, o
    l'unico modo di riaverne una e' riprovare piu' tardi, non restare fermi
    ad aspettare. Chi chiama distingue i due casi guardando prima `usable()`.
    """
    moment = time.monotonic() if now is None else now
    # Solo le pause brevi: lo stop giornaliero non entra qui, altrimenti lo
    # stream si metterebbe a dormire mezz'ora davanti a chi ha fatto la domanda.
    pauses = [
        until for key, until in _paused.items()
        if until > moment and _exhausted.get(key, 0.0) <= moment
    ]
    return min(pauses) - moment if pauses else None


def mark_exhausted(key: str | None) -> None:
    """La chiave ha finito la quota giornaliera: fuori dal giro, e riprovata
    fra mezz'ora nel caso Google l'abbia nel frattempo riabilitata."""
    if key:
        _exhausted[key] = time.monotonic() + EXHAUSTED_RETRY_S


def mark_paused(key: str | None, seconds: float) -> None:
    """La chiave ha toccato il limite al minuto: in pausa, non esaurita."""
    if key:
        _paused[key] = time.monotonic() + seconds


def status() -> dict[str, Any]:
    """Riassunto per /api/health: se una demo si ferma, si vede subito perche'."""
    moment = time.monotonic()
    return {
        "total": len(all_keys()),
        "usable": sum(1 for k in all_keys() if not _blocked(k, moment)),
        # "esaurite adesso", non "esaurite oggi": fra mezz'ora vengono riprovate
        "exhausted": sum(1 for until in _exhausted.values() if until > moment),
    }
