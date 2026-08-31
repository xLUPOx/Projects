"""API dell'assistente sul catasto del verde.

L'endpoint centrale e' /api/chat: non ritorna una risposta sola alla fine, ma
uno stream SSE di eventi. Serve al frontend per mostrare cosa sta facendo
l'agente mentre lo fa (quale tool, con quali argomenti) e per ricevere, in
chiusura, le citazioni e gli id degli alberi da evidenziare sulla mappa.

Eventi emessi (uno per riga 'data:'):
    status  -> l'agente sta per eseguire un tool
    tool    -> il tool ha risposto (sintesi dell'esito)
    text    -> delta di testo della risposta
    end     -> citazioni, alberi coinvolti, dati per il grafico
    error   -> qualcosa e' andato storto
"""
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

import cadastre
import keys
import rag
import tools

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verde-agent")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MAX_AGENT_TURNS = 6
MAX_429_RETRIES = 3

# Zero creativita': qui non si scrive, si riferisce. La stessa domanda sugli
# stessi dati deve dare la stessa risposta, altrimenti la suite eval — che
# giudica per sottostringa — misura il campionamento invece dell'agente, e in
# demo la seconda esecuzione della stessa domanda non somiglia alla prima.
TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))

ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

# Il prompt resta in italiano: e' la lingua in cui l'assistente deve rispondere.
INSTRUCTIONS = """
Sei l'assistente del catasto del verde urbano di Bolzano. Parli italiano.

REGOLE NON NEGOZIABILI
1. Rispondi SOLO con dati ottenuti dai tool. Non usare conoscenza pregressa su
   Bolzano, sugli alberi o sulle normative reali.
2. Se i tool non contengono il dato richiesto, dillo esplicitamente:
   "Questo dato non e' presente nel catasto" e spiega in una riga cosa manca.
   Non stimare, non approssimare, non inventare.
3. Cita sempre la fonte: il codice degli alberi (es. ALB-0042) per i dati del
   catasto, il riferimento dell'articolo (es. Art. 10) per il regolamento.
4. Se un tool restituisce 'total_matching' maggiore di 'returned', di' il
   totale reale e precisa che stai elencando solo i primi.
5. Per domande normative usa consult_regulation, mai la tua memoria.
6. Se un nome di quartiere, specie o luogo potrebbe non esistere, chiama prima
   allowed_values invece di tirare a indovinare.
7. Usa cadastre_stats SOLO quando la domanda chiede una ripartizione: una
   distribuzione, un confronto fra categorie, un "quanti per ogni ...". Per un
   conteggio che ha una sola risposta numerica usa search_trees e fermati li':
   non aggiungere quadri d'insieme che nessuno ha chiesto.
8. Non disegnare MAI grafici, barre o tabelle nel testo, e non usare blocchi di
   codice. Se serve un grafico, chiama cadastre_stats: il grafico lo disegna
   l'interfaccia. Nel testo limitati a una riga di commento.

STILE
Risposte brevi e operative, adatte a un tecnico dell'ufficio verde. Usa elenchi
puntati quando citi piu' di tre alberi. Niente preamboli.
Quando elenchi alberi, ogni riga ha sempre la stessa forma, anche se la domanda
era un semplice conteggio:
  - ALB-0048 - Pino nero (*Pinus nigra*), classe C, ultima ispezione 23/03/2024
Includi solo i campi che il tool ha restituito e che servono alla domanda; se la
domanda riguarda distanza o ispezione, aggiungili in coda alla riga.
Scrivi i codici e gli articoli sempre in chiaro (ALB-0048, Art. 4), mai dentro
asterischi: l'interfaccia li trasforma in targhette cliccabili.

Data odierna: {today}
"""


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    text: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


# Un client per chiave, piu' quello attivo. La rotazione la decide `keys`,
# che non conosce l'SDK: qui si tiene solo la corrispondenza chiave -> client.
_clients: dict[str, genai.Client] = {}
_client: genai.Client | None = None
_active_key: str | None = None


def _switch_key() -> bool:
    """Rende attiva una chiave utilizzabile adesso. False se non ce ne sono."""
    global _client, _active_key
    key = keys.usable()
    if key is None or key not in _clients:
        return False
    _active_key, _client = key, _clients[key]
    return True


def startup() -> None:
    """Carica i dati e apre i client. Chiamata dal lifespan, ma resta una
    funzione normale perche' `eval/run.py` gira senza server e la invoca."""
    global _clients, _client, _active_key
    cadastre.initialize()
    rag.initialize()

    _clients = {key: genai.Client(api_key=key) for key in keys.load()}
    _client, _active_key = None, None
    if not _switch_key():
        logger.warning(
            "Nessuna chiave Gemini (GEMINI_API_KEYS o GEMINI_API_KEY): "
            "/api/chat rispondera' con un errore esplicito."
        )
    else:
        logger.info("Chiavi Gemini caricate: %d", len(_clients))
    logger.info("Catasto e regolamento caricati (RAG in modalita' %s)", rag.mode())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    startup()
    yield


app = FastAPI(
    title="Assistente Catasto del Verde",
    description="Chat ancorata ai dati del catasto alberi, con citazioni e mappa sincronizzata.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL,
        "llm_configured": _client is not None,
        "keys": keys.status(),
        "rag": rag.mode(),
        "trees_loaded": cadastre.registry()["total_trees"],
    }


@app.get("/api/cadastre")
def full_cadastre() -> dict[str, Any]:
    """GeoJSON di tutti gli alberi: primo rendering della mappa."""
    return cadastre.all_geojson()


@app.get("/api/places")
def place_list() -> list[dict[str, Any]]:
    return cadastre.places()


@app.get("/api/registry")
def registry() -> dict[str, Any]:
    return cadastre.registry()


def _event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _summarize_result(name: str, result: dict[str, Any]) -> str:
    """Una riga leggibile da mostrare in chat sotto la chiamata al tool."""
    if "error" in result:
        return result["error"]
    if "total_matching" in result:
        return f"{result['total_matching']} alberi corrispondenti"
    if "articles" in result:
        references = ", ".join(a["reference"] for a in result["articles"])
        return f"{result['found']} articoli ({references})" if references else "nessun articolo"
    if "counts" in result:
        return f"{len(result['counts'])} gruppi"
    if "total_trees" in result:
        return f"{result['total_trees']} alberi a catasto"
    return "ok"


def _history_to_contents(request: ChatRequest) -> list[types.Content]:
    contents: list[types.Content] = []
    for m in request.history[-8:]:
        role = "user" if m.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m.text)]))
    contents.append(
        types.Content(role="user", parts=[types.Part(text=request.question)])
    )
    return contents


def _article_cited(reference: str, text: str) -> bool:
    """Vero se l'articolo compare davvero nella risposta.

    Tollera 'Art. 10', 'Art.10', 'articolo 10': quello che conta e' il numero.
    Il confine di parola serve a non far pescare 'Art. 5' da 'Art. 50'.
    """
    number = re.sub(r"\D", "", reference)
    return bool(number) and bool(
        re.search(rf"\bart(?:\.|icolo)?\s*{number}\b", text, flags=re.IGNORECASE)
    )


# Il titolo del grafico lo legge l'utente: i nomi dei campi tornano in italiano.
_FIELD_LABELS = {
    "risk_class": "classe di rischio",
    "district": "quartiere",
    "species": "specie",
    "common_name": "nome comune",
    "health_status": "stato fitosanitario",
}


def _collect_references(
    results: list[tuple[str, dict[str, Any]]], text: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    """Estrae dalle risposte dei tool cio' che serve al frontend per le citazioni.

    Gli alberi restituiti tornano tutti: servono ad accendere la mappa, che
    mostra su cosa ha guardato l'agente. Quali di questi meritino una targhetta
    fra le fonti lo decide il frontend, tenendo solo quelli che il testo nomina
    davvero — un albero sondato da una ricerca a vuoto non e' la fonte di
    niente. Gli articoli invece si filtrano gia' qui, perche' non hanno un
    corrispettivo sulla mappa: un articolo recuperato dal RAG ma non usato nella
    risposta e' solo un residuo della ricerca, e mostrarlo fra le fonti rompe il
    patto per cui ogni targhetta corrisponde a un'affermazione.
    """
    trees: dict[str, dict[str, Any]] = {}
    articles: dict[str, dict[str, Any]] = {}
    chart: dict[str, Any] | None = None

    for name, result in results:
        for tree in result.get("trees", []):
            trees[tree["id"]] = {
                "id": tree["id"],
                "common_name": tree["common_name"],
                "species": tree["species"],
                "district": tree["district"],
                "risk_class": tree["risk_class"],
                "months_since_inspection": tree["months_since_inspection"],
                "lat": tree["lat"],
                "lng": tree["lng"],
            }
        for article in result.get("articles", []):
            if _article_cited(article["reference"], text):
                articles[article["reference"]] = article
        if name == "cadastre_stats" and "counts" in result:
            chart = {
                "title": f"Alberi per {_FIELD_LABELS.get(result['group_by'], result['group_by'])}",
                # I filtri restano un campo a parte: concatenarli al titolo
                # produceva una riga lunghissima in maiuscoletto spaziato.
                "subtitle": result.get("filters") or "",
                "items": result["counts"],
            }

    return list(trees.values()), list(articles.values()), chart


QUOTA_EXHAUSTED = (
    "Quota giornaliera Gemini esaurita su tutte le chiavi configurate. Il free "
    "tier non concede altre richieste oggi: serve attivare la fatturazione su "
    "una chiave, aggiungerne un'altra in GEMINI_API_KEYS, o riprovare domani."
)


def _is_daily_quota(e: errors.ClientError) -> bool:
    """Il limite giornaliero non si supera aspettando: la chiave va messa da
    parte, non messa in pausa. Il campo che li separa e' il `quotaId`, lo stesso
    che guarda `_suggested_wait`."""
    return "PerDay" in str(e)


def _suggested_wait(e: errors.ClientError) -> float | None:
    """Secondi da aspettare prima di ritentare un 429, o None se e' inutile.

    La distinzione che conta e' fra il limite al minuto e quello giornaliero:
    il primo si supera aspettando, il secondo no. Non basta guardare il
    `retryDelay`, perche' Gemini lo manda in entrambi i casi (sul limite
    giornaliero dice 59s, che e' una promessa che non puo' mantenere). Il campo
    che li separa davvero e' il `quotaId`, che contiene 'PerDay' o 'PerMinute'.

    Cerco nella rappresentazione testuale invece di navigare `details`: la forma
    del payload cambia tra versioni dell'SDK, i nomi dei campi no.
    """
    text = str(e)
    if "PerDay" in text:
        return None
    match = re.search(r"retryDelay['\"]?[:=]\s*['\"]?(\d+(?:\.\d+)?)s", text)
    return float(match.group(1)) + 1 if match else None


def _chunks_with_retry(
    contents: list[types.Content], config: types.GenerateContentConfig
) -> Iterator[Any]:
    """Stream dei chunk, con retry sul 429.

    Il free tier di Gemini concede poche richieste al minuto, e il ciclo
    dell'agente ne consuma 2-3 per singola domanda: senza retry, una
    conversazione con qualche scambio incontra la quota quasi da subito.

    Con piu' chiavi configurate la prima mossa non e' aspettare ma cambiare
    chiave, che costa zero secondi. Si dorme solo quando sono tutte al limite
    del minuto, e si rinuncia solo quando sono tutte esaurite per la giornata.
    """
    attempts = len(keys.all_keys()) + MAX_429_RETRIES
    for attempt in range(attempts):
        emitted = False
        try:
            for chunk in _client.models.generate_content_stream(
                model=MODEL, contents=contents, config=config
            ):
                emitted = True
                yield chunk
            return
        except errors.ClientError as e:
            # Se avevamo gia' emesso chunk non possiamo ritentare — ne' con la
            # stessa chiave ne' con un'altra — senza duplicare il testo.
            if e.code != 429 or emitted or attempt == attempts - 1:
                raise

            if _is_daily_quota(e):
                logger.warning("Quota giornaliera finita su una chiave, passo alla prossima")
                keys.mark_exhausted(_active_key)
            else:
                keys.mark_paused(_active_key, _suggested_wait(e) or 30.0)

            if _switch_key():
                continue  # un'altra chiave e' libera adesso: niente attesa

            wait = keys.wait_time()
            if wait is None:
                raise  # nessuna chiave tornera' libera oggi
            logger.warning("Tutte le chiavi al limite, riprovo tra %.0fs", wait)
            time.sleep(wait)
            if not _switch_key():
                raise


def _stream_agent(request: ChatRequest) -> Iterator[str]:
    if _client is None:
        yield _event({
            "type": "error",
            "message": "GEMINI_API_KEY non configurata: crea backend/.env a partire da .env.example.",
        })
        return

    config = types.GenerateContentConfig(
        tools=list(tools.TOOLS.values()),
        temperature=TEMPERATURE,
        # AFC disabilitata: il ciclo lo guidiamo noi, e' l'unico modo per
        # emettere un evento per ogni singola chiamata mentre avviene.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        # La data del catasto, non quella di sistema: i mesi trascorsi dalle
        # ispezioni sono contati da li', e dire al modello un "oggi" diverso
        # gli farebbe sbagliare qualunque conto sulle scadenze.
        system_instruction=INSTRUCTIONS.format(
            today=cadastre.reference_date().isoformat()
        ),
    )

    contents = _history_to_contents(request)
    results: list[tuple[str, dict[str, Any]]] = []
    tools_used: list[str] = []
    # Serve a fine corsa per sapere quali articoli il modello ha davvero citato.
    final_text = ""

    try:
        for turn in range(MAX_AGENT_TURNS):
            model_parts: list[types.Part] = []
            calls: list[Any] = []

            for chunk in _chunks_with_retry(contents, config):
                candidate = (chunk.candidates or [None])[0]
                if candidate is None or candidate.content is None:
                    continue
                for part in candidate.content.parts or []:
                    model_parts.append(part)
                    if part.text:
                        final_text += part.text
                        yield _event({"type": "text", "delta": part.text})
                    if part.function_call:
                        calls.append(part.function_call)

            if not calls:
                break

            contents.append(types.Content(role="model", parts=model_parts))

            result_parts = []
            for call in calls:
                args = dict(call.args or {})
                label = tools.LABELS.get(call.name, call.name)
                yield _event({
                    "type": "status",
                    "name": call.name,
                    "text": label,
                    "args": args,
                })

                function = tools.TOOLS.get(call.name)
                if function is None:
                    result: dict[str, Any] = {"error": f"Tool sconosciuto: {call.name}"}
                else:
                    try:
                        result = function(**args)
                    except TypeError as e:
                        # Argomenti fuori schema: rimandiamo l'errore al modello,
                        # che nella maggior parte dei casi ritenta correggendosi.
                        result = {"error": f"Argomenti non validi: {e}"}

                results.append((call.name, result))
                tools_used.append(call.name)
                yield _event({
                    "type": "tool",
                    "name": call.name,
                    "args": args,
                    "result": _summarize_result(call.name, result),
                })
                result_parts.append(
                    types.Part.from_function_response(name=call.name, response=result)
                )

            contents.append(types.Content(role="user", parts=result_parts))
        else:
            logger.warning("Raggiunto il limite di %s turni agente", MAX_AGENT_TURNS)

        trees, articles, chart = _collect_references(results, final_text)
        yield _event({
            "type": "end",
            "trees": trees,
            "articles": articles,
            "chart": chart,
            "tools_used": tools_used,
        })

    except errors.APIError as e:
        logger.exception("Errore dall'API Gemini")
        # Esaurito davvero: nessuna chiave libera adesso e nessuna che torni
        # libera aspettando.
        quota_over = (
            e.code == 429 and keys.usable() is None and keys.wait_time() is None
        )
        yield _event({
            "type": "error",
            "message": QUOTA_EXHAUSTED if quota_over else f"Errore Gemini: {e.message}",
            "quota": quota_over,
        })
    except Exception as e:  # noqa: BLE001
        logger.exception("Errore imprevisto nello stream")
        yield _event({"type": "error", "message": f"Errore interno: {e}"})


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream_agent(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
