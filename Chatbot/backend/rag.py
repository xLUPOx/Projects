"""RAG sul regolamento comunale del verde.

Due retriever, stessa interfaccia:
  - semantico, con gli embedding di Gemini (default se c'e' la API key);
  - lessicale BM25 Okapi (rank_bm25) su token stemmati con Snowball italiano,
    usato come fallback automatico.

Il fallback non e' un ripiego pigro: il documento e' piccolo e strutturato per
articoli, quindi BM25 regge la demo anche offline e rende i test deterministici.
Ogni chunk e' un articolo, cosi' la citazione restituita all'utente e' proprio
il riferimento normativo ("Art. 10") e non un offset di caratteri.
"""
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import snowballstemmer
from rank_bm25 import BM25Okapi

import keys

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCUMENT = DATA_DIR / "regolamento_verde.md"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

_chunks: list[dict[str, Any]] = []
_vectors: np.ndarray | None = None  # matrice (n_chunk x dim) a righe normalizzate
_mode = "non inizializzato"

# BM25: k1 governa la saturazione della frequenza, b quanto pesa la lunghezza
# del documento. Sono i default di rank_bm25, li passo espliciti perche' sono
# i due parametri che si toccano davvero quando si ritara un retriever.
_K1, _B = 1.5, 0.75
_bm25: BM25Okapi | None = None

STOP_WORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da",
    "in", "con", "su", "per", "tra", "fra", "del", "dello", "della", "dei",
    "degli", "delle", "al", "allo", "alla", "ai", "agli", "alle", "dal",
    "dalla", "nel", "nella", "nei", "sul", "sulla", "e", "ed", "o", "che",
    "non", "si", "ogni", "come", "quanto", "quale", "quali", "essere", "sono",
    "va", "vanno", "puo", "deve", "devono", "piu", "meno", "cosa", "quando",
    # parole vuote *di questo corpus*: l'intero documento e' il regolamento di
    # un comune, quindi "comunale" non distingue un articolo dall'altro. Senza
    # questa riga "gli orari della biblioteca comunale" pesca l'Art. 1 e la
    # soglia non basta piu' a scartarlo.
    "comune", "comunale", "comunali",
}


_STEMMER = snowballstemmer.stemmer("italian")


def _tokenize(text: str) -> list[str]:
    """Parole -> radici con lo stemmer Snowball italiano, cosi' la domanda e il
    regolamento si incontrano anche quando usano forme diverse della stessa
    parola (abbattere/abbattimento -> abbatt, ispezione/ispezionati -> ispezion,
    distanza/distanze -> distanz)."""
    words = re.findall(r"\w+", text.lower())
    return _STEMMER.stemWords([w for w in words if w not in STOP_WORDS and len(w) > 2])


def _split_into_articles(text: str) -> list[dict[str, Any]]:
    """Ogni '## Art. N - Titolo' diventa un chunk citabile."""
    chunks = []
    blocks = re.split(r"\n(?=## )", text)
    for block in blocks:
        block = block.strip()
        if not block.startswith("## "):
            continue
        first_line, _, body = block.partition("\n")
        title = first_line.removeprefix("## ").strip()
        body = " ".join(body.split())
        if not body:
            continue
        match = re.match(r"(Art\.\s*\d+)", title)
        chunks.append({
            "reference": match.group(1) if match else title,
            "title": title,
            "text": body,
            "source": DOCUMENT.name,
        })
    return chunks


def initialize() -> None:
    """Carica il documento e prepara gli indici. Idempotente."""
    global _chunks, _vectors, _mode, _bm25
    if _chunks:
        return

    _chunks = _split_into_articles(DOCUMENT.read_text(encoding="utf-8"))
    for c in _chunks:
        c["tokens"] = _tokenize(c["title"] + " " + c["text"])

    _bm25 = BM25Okapi([c["tokens"] for c in _chunks], k1=_K1, b=_B)

    embeddings = _try_embeddings([c["title"] + ". " + c["text"] for c in _chunks])
    _vectors = _normalize(embeddings) if embeddings else None
    _mode = "embedding Gemini" if _vectors is not None else "BM25 lessicale"


def _try_embeddings(texts: list[str]) -> list[list[float]] | None:
    """Ritorna None (e la ricerca passa a BM25) se non c'e' nessuna chiave
    utilizzabile o se falliscono tutte.

    Prova le chiavi in ordine: la quota degli embedding e' un secchio a parte
    rispetto a quella della generazione, quindi qui non si guarda quali chiavi
    main ha gia' messo da parte — una chiave esaurita per generare puo' avere
    ancora margine per indicizzare.
    """
    pool = keys.all_keys()
    if not pool:
        return None

    from google import genai

    for key in pool:
        try:
            client = genai.Client(api_key=key)
            response = client.models.embed_content(model=EMBEDDING_MODEL, contents=texts)
            return [list(e.values) for e in response.embeddings]
        except Exception as e:  # noqa: BLE001 - il fallback e' voluto
            print(f"[rag] chiave non utilizzabile per gli embedding ({e})")
    print("[rag] nessuna chiave utilizzabile per gli embedding; uso BM25.")
    return None


def _normalize(vectors: list[list[float]]) -> np.ndarray:
    """Matrice float32 con le righe portate a norma 1."""
    m = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0.0, 1.0, norms)


def _similarity(query_vector: list[float], matrix: np.ndarray) -> list[float]:
    """Coseno fra la domanda e tutti i chunk in un solo prodotto matrice-vettore.
    Con le righe gia' normalizzate il coseno e' il prodotto scalare, che e'
    esattamente quello che fa un vector store sotto il cofano."""
    return (matrix @ _normalize([query_vector])[0]).tolist()


def _bm25_scores(question: str) -> list[float]:
    """Punteggio BM25 Okapi della domanda contro ogni articolo."""
    return _bm25.get_scores(_tokenize(question)).tolist()


# Soglie assolute: sotto queste il chunk non e' pertinente e viene scartato,
# anche se e' il migliore disponibile. E' cio' che permette al modello di
# rispondere "il regolamento non lo prevede" invece di citare l'articolo meno
# peggio. Le due scale sono diverse, quindi le soglie sono due.
# La soglia BM25 e' calibrata sui casi di test_rag.py: le domande fuori dominio
# arrivano a 0.0, la peggiore domanda legittima a 2.2. Va ritarata se cambia il
# corpus, il tokenizzatore o k1/b: cambiando quelli cambia la scala dei
# punteggi, non solo il loro ordine.
BM25_THRESHOLD = 2.0
COSINE_THRESHOLD = 0.55

# Tetto, non obiettivo: la soglia sopra puo' ridurli a zero. Tre copre le
# domande a cavallo di due articoli (Art. 10 e Art. 11 sulla potatura), e
# alzarlo si paga in precisione: articoli marginali che il modello poi cita.
MAX_ARTICLES = 3


def search(question: str, n_results: int = MAX_ARTICLES) -> dict[str, Any]:
    """Restituisce gli articoli piu' pertinenti, gia' pronti per essere citati."""
    initialize()

    query_vector = _try_embeddings([question]) if _vectors is not None else None
    if query_vector:
        scores = _similarity(query_vector[0], _vectors)
        threshold = COSINE_THRESHOLD
    else:
        scores = _bm25_scores(question)
        threshold = BM25_THRESHOLD

    ranked = sorted(zip(scores, _chunks), key=lambda x: x[0], reverse=True)
    best = ranked[0][0] if ranked else 0.0

    results = []
    for score, c in ranked[:n_results]:
        if score < threshold:
            continue
        results.append({
            "reference": c["reference"],
            "title": c["title"],
            "text": c["text"],
            "source": c["source"],
            # normalizzata sul migliore, solo per mostrarla in interfaccia
            "relevance": round(score / best, 3) if best else 0.0,
            "raw_score": round(score, 3),
        })

    return {
        "search_mode": _mode,
        "found": len(results),
        "articles": results,
        "notice": None if results else "Nessun articolo pertinente nel regolamento.",
    }


def mode() -> str:
    initialize()
    return _mode
