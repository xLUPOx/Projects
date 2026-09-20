"""
MuseumLangAPI - riconoscimento della lingua di testi museali, versione di produzione
====================================================================================

Servizio HTTP che riceve la didascalia di un'opera e restituisce il codice della lingua
in cui è scritta, con la probabilità che il modello le assegna. È la versione destinata
al deploy su una piattaforma serverless (Vercel): rispetto alla versione locale il
modello si carica nel lifespan, i percorsi nascono da __file__ e il registro va sullo
standard output, perché il filesystem di una funzione serverless non è scrivibile.

Funzionalità principali:
  1. POST /identify-language riceve {"text": "..."} e risponde
     {"language_code": "IT", "confidence": 0.98}.
  2. Testo vuoto o di soli spazi: 400. Lingua non identificata: 409. Corpo malformato,
     campo sconosciuto o testo oltre MAX_TEXT_LENGTH: 422, prodotto da Pydantic.
  3. Ogni richiesta e ogni risposta finiscono nel registro, comprese le richieste che
     Pydantic rifiuta prima che raggiungano la funzione dell'endpoint.
  4. GET /health dice se il modello è caricato, senza chiamarlo.
  5. GET / elenca gli endpoint e mostra come provarli, così chi apre l'indirizzo in un
     browser non trova un 404.

Architettura presente nello script:
  - CONFIGURATION    costanti di servizio, tutte rilette altrove nel file
  - LOGGING          registro su standard output, raccolto dalla piattaforma
  - MODEL            caricamento nel lifespan e previsione
  - SCHEMAS          corpo della richiesta e della risposta, da cui nasce OpenAPI
  - INDEX PAGE       modello della pagina servita su /
  - ERROR HANDLERS   registrazione delle richieste respinte dalla validazione
  - ENDPOINTS        /, /identify-language e /health

Istruzioni per l'uso:
  In locale:  pip install -r requirements.txt
              python app.py          (su Windows: py app.py)
              la documentazione interattiva sta su /docs

  In produzione: la piattaforma importa la variabile `app` di questo file e si occupa
  lei dell'ascolto; HOST e PORT valgono solo per l'avvio locale qui sotto.

Requisiti: Python 3.12+, le dipendenze di requirements.txt. Il file
language_detection_pipeline.pkl deve stare accanto a questo script.

Al fondo: NOTE DI PROGETTO - scelte, semplificazioni e sviluppi futuri
"""

import logging
import os
import pickle
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------

# The model sits next to this file, not in the current working directory: a serverless
# platform starts the function from the project root, so a relative name would not be
# found there.
MODEL_FILE = Path(__file__).parent / "language_detection_pipeline.pkl"

# Below this confidence the language counts as not identified. Read by
# identify_language and quoted in the 409 message: changing it here changes both.
MIN_CONFIDENCE = 0.5

# Longest accepted caption. Read by LanguageRequest, so a text over this length is
# refused by validation before reaching the model, which would otherwise spend the
# whole request vectorising it.
MAX_TEXT_LENGTH = 5000

# Only used by the local launch at the bottom of this file: in production the platform
# binds the socket. They come from the environment so that a run on another machine can
# move them without touching the code.
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# --------------------------------------------------------------------------
# LOGGING
# --------------------------------------------------------------------------

# scriviamo il registro sullo standard output invece che su file
# A serverless function has no writable project directory and is rebuilt at every
# deploy, so a log file would be both impossible to open and lost. The platform reads
# stdout as the log of the request.
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s | %(message)s")
logger = logging.getLogger("museum_lang_api")

# --------------------------------------------------------------------------
# MODEL
# --------------------------------------------------------------------------

# Filled by the lifespan below and read by identify_language and health. It is a dict
# and not a bare global because the lifespan has to rebind it after this module is
# imported, and rebinding a name inside a function would create a local one.
state = {}


@asynccontextmanager
async def lifespan(app):
    """
    Carica il modello all'avvio del servizio e lo libera allo spegnimento.

    Loading here rather than at import time means one load per instance instead of one
    per request, and a failure surfaces while the platform is still starting the
    function. If the file is missing the exception stops the startup: without a model
    the service has nothing to answer with, so failing now is preferable to failing on
    the first caller.
    """
    logger.info("AVVIO: carico il modello da %s", MODEL_FILE.name)
    with open(MODEL_FILE, "rb") as handle:
        state["model"] = pickle.load(handle)
    logger.info("AVVIO: modello pronto, lingue riconosciute %s",
                list(state["model"].classes_))
    yield
    state.clear()


def predict_language(text):
    """
    Restituisce (codice lingua, confidenza) per un testo.

    Both values are read from the same row of probabilities: taking the label from
    predict() and the number from predict_proba() would let the two contradict each
    other if the model ever broke ties differently between the two calls.
    """
    probabilities = list(state["model"].predict_proba([text])[0])
    confidence = max(probabilities)
    language_code = str(state["model"].classes_[probabilities.index(confidence)])
    return language_code, round(float(confidence), 4)


# --------------------------------------------------------------------------
# SCHEMAS
# --------------------------------------------------------------------------

class LanguageRequest(BaseModel):
    """Corpo della richiesta: il testo di cui riconoscere la lingua."""

    # extra="forbid": a body with an unknown field is refused instead of being
    # accepted with that field silently ignored, which would hide a caller typo.
    model_config = {"extra": "forbid"}

    text: str = Field(..., max_length=MAX_TEXT_LENGTH,
                      description="Text whose language has to be identified.",
                      examples=["Statua in marmo di un imperatore romano."])


class LanguageResponse(BaseModel):
    """Corpo della risposta: codice della lingua e confidenza."""

    language_code: str = Field(..., description="Language code: IT, DE or EN.",
                               examples=["IT"])
    confidence: float = Field(..., description="Probability assigned to that language.",
                              examples=[0.98])


# --------------------------------------------------------------------------
# INDEX PAGE
# --------------------------------------------------------------------------

# Il modello della pagina che risponde su "/", con i valori presi dalle costanti sopra.
# MIN_CONFIDENCE and MAX_TEXT_LENGTH are interpolated rather than written out, so that
# changing a constant changes what the page promises. The base address is left as a
# placeholder and filled per request: a serverless deploy gets a new URL every time, and
# writing one here would make the page quote a stale address.
INDEX_TEMPLATE = """<!doctype html>
<html lang="it">
<meta charset="utf-8">
<title>MuseumLangAPI</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 42rem; margin: 3rem auto;
         padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }
  code, pre { background: #f4f4f5; border-radius: 4px; }
  code { padding: .1rem .3rem; }
  pre { padding: .8rem; overflow-x: auto; }
  h1 { margin-bottom: .2rem; }
  .sub { color: #666; margin-top: 0; }
  table { border-collapse: collapse; width: 100%%; margin: 1rem 0; }
  th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #e4e4e7; }
  a { color: #0645ad; }
</style>
<h1>MuseumLangAPI</h1>
<p class="sub">Riconoscimento della lingua delle didascalie museali: italiano, inglese
e tedesco.</p>

<h2>Endpoint</h2>
<table>
  <tr><th>metodo</th><th>percorso</th><th>cosa fa</th></tr>
  <tr><td>POST</td><td><code>/identify-language</code></td>
      <td>riceve un testo e risponde con la lingua e la confidenza</td></tr>
  <tr><td>GET</td><td><a href="/health"><code>/health</code></a></td>
      <td>dice se il modello è caricato</td></tr>
  <tr><td>GET</td><td><a href="/docs"><code>/docs</code></a></td>
      <td>documentazione interattiva, da cui si provano le chiamate</td></tr>
</table>

<h2>Come si prova</h2>
<p>Il modo più rapido è <a href="/docs">/docs</a>: si apre
<code>POST /identify-language</code>, si preme <em>Try it out</em>, si scrive il testo
e si esegue. Da riga di comando:</p>
<pre>curl -X POST %(base)s/identify-language \\
     -H "Content-Type: application/json" \\
     -d '{"text": "Statua in marmo di un imperatore romano."}'</pre>
<p>La risposta è <code>{"language_code": "IT", "confidence": 0.98}</code>.</p>
<!-- %(base)s viene dalla richiesta: l&rsquo;indirizzo cambia a ogni deploy. -->

<h2>Esiti possibili</h2>
<table>
  <tr><th>codice</th><th>quando</th></tr>
  <tr><td>200</td><td>lingua riconosciuta</td></tr>
  <tr><td>400</td><td>il campo <code>text</code> è vuoto o di soli spazi</td></tr>
  <tr><td>409</td><td>confidenza sotto %(soglia)s: lingua non identificata</td></tr>
  <tr><td>422</td><td>corpo malformato, campo sconosciuto, o testo oltre %(maxlen)s
      caratteri</td></tr>
</table>
""".replace("%(soglia)s", str(MIN_CONFIDENCE)).replace("%(maxlen)s", str(MAX_TEXT_LENGTH))

# --------------------------------------------------------------------------
# ERROR HANDLERS
# --------------------------------------------------------------------------

app = FastAPI(
    title="MuseumLangAPI",
    description="Riconoscimento della lingua delle didascalie museali.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def log_validation_error(request, exc):
    """
    Registra le richieste che la validazione rifiuta, poi lascia rispondere FastAPI.

    Without this handler a body refused by Pydantic never reaches identify_language and
    so leaves no trace at all: the audit would be missing exactly the malformed calls it
    exists to document. exc.body carries the payload that was refused, so the request
    does not have to be read a second time.
    """
    caller = request.client.host if request.client else "unknown"
    logger.info("RICHIESTA da %s rifiutata dalla validazione: %s", caller, exc.body)
    logger.info("RISPOSTA 422: %s", exc.errors())
    return await request_validation_exception_handler(request, exc)


# --------------------------------------------------------------------------
# ENDPOINTS
# --------------------------------------------------------------------------

@app.post("/identify-language", responses={
    400: {"description": "Il campo 'text' è vuoto."},
    409: {"description": "Lingua non identificata: confidenza sotto la soglia."},
})
def identify_language(payload: LanguageRequest, request: Request) -> LanguageResponse:
    """Riconosce la lingua di un testo e la restituisce con la confidenza."""
    caller = request.client.host if request.client else "unknown"
    logger.info("RICHIESTA da %s: %s", caller, payload.text)

    text = payload.text.strip()
    if not text:
        message = "Il campo 'text' è vuoto: non c'è niente da riconoscere."
        logger.info("RISPOSTA 400: %s", message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    language_code, confidence = predict_language(text)
    if confidence < MIN_CONFIDENCE:
        message = ("Lingua non identificata: confidenza %s sotto la soglia %s."
                   % (confidence, MIN_CONFIDENCE))
        logger.info("RISPOSTA 409: %s", message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

    answer = LanguageResponse(language_code=language_code, confidence=confidence)
    logger.info("RISPOSTA 200: %s", answer.model_dump())
    return answer


@app.get("/health")
def health():
    """Dice se il modello è caricato, senza interrogarlo."""
    loaded = "model" in state
    return {"status": "ok" if loaded else "loading", "model_loaded": loaded}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    """
    Indice del servizio: elenca gli endpoint e mostra come provarli.

    A caller who opens the base address in a browser would otherwise get a bare 404:
    the API answers only on its own paths, and nothing says where they are. The address
    in the curl example comes from the request and not from a constant, because a
    serverless deploy gets a new URL every time and a written one would go stale.
    """
    base = str(request.base_url).rstrip("/")
    return INDEX_TEMPLATE.replace("%(base)s", base)


if __name__ == "__main__":
    import uvicorn

    print("MuseumLangAPI su http://%s:%d  (documentazione su /docs)" % (HOST, PORT))
    uvicorn.run(app, host=HOST, port=PORT)


"""
NOTE DI PROGETTO - scelte, semplificazioni e sviluppi futuri
============================================================

Questa sezione documenta le decisioni prese in fase di sviluppo e i limiti consapevoli
dell'applicativo, per distinguere ciò che è una scelta di progetto da ciò che sarebbe
un difetto.

Scelte di semplificazione o aggiuntive
-------------------------

1. Modello caricato nel lifespan invece che a livello di modulo.
   Il caricamento sta in una funzione marcata con @asynccontextmanager e passata a
   FastAPI(lifespan=...), la forma che sostituisce @app.on_event("startup"), oggi
   deprecato. Caricare all'import funzionava, ma legava il modello al momento in cui
   il file viene letto: nel lifespan il modello viene caricato una volta per istanza
   del servizio, e un errore si manifesta mentre la piattaforma sta ancora avviando la
   funzione, non davanti al primo chiamante. Il limite noto è che una piattaforma
   serverless spegne e riaccende le istanze a sua discrezione: il caricamento si paga
   di nuovo a ogni avvio a freddo, circa un secondo, che ricade sulla prima richiesta
   di quell'istanza.

2. Percorso del modello costruito da __file__ e non dalla cartella corrente.
   La versione locale apriva "language_detection_pipeline.pkl" per nome e andava quindi
   lanciata dalla cartella in cui il file si trovava. Una funzione serverless parte
   invece dalla radice del progetto, che non è la cartella di questo file: con il nome
   relativo il modello non verrebbe trovato. Path(__file__).parent lo àncora al file e
   toglie del tutto il vincolo su da dove si lancia il programma.

3. Registro sullo standard output invece che su api.log.
   Il filesystem di una funzione serverless non è scrivibile e viene ricostruito a ogni
   deploy: un file di log sarebbe insieme impossibile da aprire e destinato a sparire.
   La piattaforma raccoglie invece ciò che il processo scrive su standard output e lo
   presenta raggruppato per richiesta. Cade con questa scelta anche il motivo per cui
   la versione locale dichiarava encoding="utf-8" sul registro: senza un file da
   codificare il parametro non ha più oggetto. Il limite noto è che la conservazione
   dipende dal piano della piattaforma e sul piano gratuito è di un'ora: per un audit
   che deve durare va collegato un servizio esterno di raccolta, e le righe sono
   contate, 256 per richiesta.

4. Richieste respinte dalla validazione registrate da un handler dedicato.
   Un corpo che Pydantic rifiuta non arriva mai alla funzione dell'endpoint, quindi
   nella versione locale non lasciava alcuna traccia: il registro documentava tutte le
   chiamate tranne proprio quelle malformate. L'handler su RequestValidationError
   scrive la richiesta e l'esito, poi delega la risposta a
   request_validation_exception_handler, così il corpo dell'errore resta quello
   standard di FastAPI. Il payload si legge da exc.body, che lo porta già con sé, e non
   rileggendo la richiesta.

5. Lingua non identificata: 409 invece di 422.
   La versione locale usava 422 per la confidenza sotto la soglia, ma 422 è anche il
   codice con cui FastAPI rifiuta d'ufficio un corpo malformato: i due casi arrivavano
   al chiamante con lo stesso numero e si distinguevano solo dalla forma di "detail",
   una stringa nel primo caso e una lista di errori nel secondo. 409 Conflict dice
   invece "richiesta ben formata, ma non lavorabile" e lascia 422 alla sola
   validazione, che se lo prende comunque. Restano quindi tre codici distinti e
   leggibili: 400 richiesta mal composta, 409 non lavorabile, 422 non valida.

6. Soglia di confidenza a 0,5, dichiarata per quello che misura.
   Con tre lingue significa che la vincente deve valere più delle altre due insieme, e
   un testo di cui il modello non riconosce nulla riceve le probabilità a priori
   (0,3417) cadendo sotto la soglia. Il limite noto è che la soglia non intercetta gli
   errori del modello, e va scritto qui perché chi legge la risposta non può dedurlo:
   una frase in una lingua che il modello non conosce riceve comunque una delle tre
   risposte, e con piena sicurezza. Misurato su questo modello, "Estatua de marmol de
   un emperador romano del siglo primero." è classificato IT con confidenza 1,0. La
   confidenza va quindi letta come quanto il testo sia informativo per un modello che
   conosce tre lingue, non come quanto la risposta sia giusta.

7. Versione di scikit-learn fissata in requirements.txt.
   Il file .pkl è stato prodotto con scikit-learn 1.6.0 e conserva la versione al
   proprio interno. Aprirlo con una versione diversa emette InconsistentVersionWarning
   e la stessa documentazione della libreria non garantisce il risultato: caricato con
   la 1.8.0 il warning compare per tutti e tre gli oggetti della pipeline. In
   requirements.txt la versione è quindi fissata con ==, non con >=.

8. Lunghezza massima del testo dichiarata nello schema.
   max_length su LanguageRequest fa respingere dalla validazione un testo oltre i 5000
   caratteri, prima che il modello lo vettorizzi. Il limite noto è che la piattaforma ne
   impone comunque uno proprio e più alto sul corpo della richiesta, 4,5 MB: quello di
   qui serve a proteggere il tempo di calcolo, non la memoria del processo.

9. Endpoint pubblico, senza chiave.
   La correzione chiedeva di rendere il servizio raggiungibile da un altro PC del museo,
   cosa che l'ascolto su loopback impediva; pubblicato su una piattaforma, però, il
   servizio non è raggiungibile solo dal museo ma da chiunque ne conosca l'indirizzo. Il
   limite noto è quindi che chiunque può interrogarlo e consumarne il tempo di calcolo:
   finché il servizio espone solo il riconoscimento della lingua di un testo che il
   chiamante già possiede non diffonde informazioni riservate, ma prima di un uso reale
   va messo dietro una chiave.

10. HOST e PORT letti dall'ambiente, ma solo per l'avvio locale.
    In produzione è la piattaforma ad aprire il socket e le due costanti non vengono
    lette: restano per chi lancia il file a mano, con 0.0.0.0 al posto di 127.0.0.1 in
    modo che il servizio risponda anche alle chiamate da un'altra macchina della rete.

11. Endpoint /health aggiunto oltre la traccia.
    Dice se il modello è caricato senza interrogarlo, così una sonda esterna può
    distinguere un servizio avviato da uno che sta ancora caricando senza pagare una
    previsione. Il limite noto è che non verifica che il modello risponda correttamente:
    dice che è in memoria, non che predice bene.

12. Pagina di indice su /, anch'essa oltre la traccia.
    Un servizio pubblicato viene aperto in un browser prima che con curl, e la radice
    rispondeva 404 perché l'API vive solo sui propri percorsi: la pagina elenca gli
    endpoint, i codici di esito e l'esempio di chiamata, e rimanda a /docs per provarli.
    L'indirizzo nell'esempio viene da request.base_url e non da una costante, perché il
    deploy ne riceve uno nuovo ogni volta. È HTML scritto a mano in una stringa, senza
    motore di template: è l'unica pagina del servizio, e Jinja sarebbe una dipendenza in
    più per lei sola. Il limite noto è che la pagina va aggiornata a mano se cambiano gli
    endpoint, mentre /docs nasce da sé dagli schemi.


Sviluppi futuri
---------------

1. Endpoint per lotti di testi, per riconoscere in una chiamata sola le didascalie di
   un'intera sala. Il modello lavora già su liste e la modifica è contenuta; non è stato
   fatto ora perché la traccia descrive un testo per richiesta e il formato della
   risposta a lotti va concordato con chi chiama.

2. Chiave API e limitazione della frequenza, oggi assenti e necessarie appena il
   servizio smette di essere una dimostrazione. Non sono state messe perché la scelta di
   chi possa chiamare il servizio appartiene a chi lo installa, non a questo file.

3. Raccolta dei log verso un servizio esterno, che li conservi oltre la finestra della
   piattaforma. Serve appena il registro debba valere come audit, cioè essere
   consultabile a distanza di mesi e non di ore.

4. Ricalibrazione della confidenza su un insieme di validazione, così che il numero
   restituito sia una probabilità leggibile e non solo un ordinamento. È lavoro da fare
   dove il modello nasce, non qui che lo riceve già addestrato.

5. Riconoscimento di un'opzione "lingua non fra quelle note", oggi impossibile: il
   modello sceglie sempre fra tre. Richiede di addestrarlo con una classe di rifiuto,
   quindi di tornare sul modello e non sul servizio.
"""
