# MuseumLangAPI — servizio REST in produzione su Vercel — riassunto

**Fonte:** `museum_lang_api_vercel/app.py`
**Caso:** lo stesso museo della versione locale, che ora vuole il riconoscimento della lingua
raggiungibile da fuori la propria macchina, senza tenere acceso un server.
**Cos'è:** la versione di produzione del servizio, pensata per una piattaforma serverless. Riceve
la didascalia di un'opera in JSON e restituisce il codice della lingua con la probabilità
assegnata dal modello.
**Requisiti:** Python 3.12, le dipendenze fissate in `requirements.txt` (`fastapi`, `uvicorn`,
`pydantic` e `scikit-learn`, che serve ad aprire la pipeline e non solo ad addestrarla). Il file
`language_detection_pipeline.pkl` deve stare accanto allo script.

**Cosa cambia rispetto alla versione locale.** La traccia è la stessa; a cambiare è il posto in
cui il programma gira, e tre vincoli di quel posto riscrivono altrettante scelte. Una funzione
serverless **non ha un filesystem scrivibile**, quindi il registro va sullo standard output invece
che su `api.log`. **Parte dalla radice del progetto** e non dalla cartella dello script, quindi il
percorso del modello nasce da `__file__` invece che da un nome relativo. **Viene spenta e
riaccesa a discrezione della piattaforma**, quindi il modello si carica nel `lifespan` — una volta
per istanza, con l'errore che emerge mentre la piattaforma sta ancora avviando la funzione.

---

## 1. Configurazione

`MODEL_FILE` è costruito come `Path(__file__).parent / "..."`: è la correzione che rende il
programma indipendente da dove viene lanciato. `MIN_CONFIDENCE` e `MAX_TEXT_LENGTH` sono lette
altrove nel file — la prima dall'endpoint e citata nel messaggio di errore, la seconda dallo
schema — e **la pagina di indice le interpola invece di riscriverle**, così cambiarle qui cambia
anche quello che la pagina promette.

`HOST` e `PORT` restano per il solo avvio locale: in produzione è la piattaforma ad aprire il
socket, e le due costanti non vengono lette.

## 2. Registro

`logging.basicConfig(stream=sys.stdout, ...)`. Cade con questa scelta anche l'`encoding="utf-8"`
che la versione locale dichiarava sul file: senza un file da codificare il parametro non ha più
oggetto. Il limite è la conservazione, che dipende dal piano della piattaforma e sul gratuito dura
un'ora.

## 3. Modello

Il caricamento sta in una funzione `@asynccontextmanager` passata a `FastAPI(lifespan=...)`, la
forma che sostituisce `@app.on_event("startup")`, deprecato. Il modello vive in un dizionario
`state` e non in una variabile globale nuda, perché il lifespan deve riassegnarlo dopo l'import e
un'assegnazione dentro una funzione creerebbe un nome locale.

`predict_language` legge codice e confidenza **dalla stessa riga di probabilità**: prendere
l'etichetta da `predict()` e il numero da `predict_proba()` lascerebbe che i due si contraddicano.

Il limite è il costo dell'avvio a freddo — circa un secondo — che ricade sulla prima richiesta di
ogni nuova istanza.

## 4. Schemi

`LanguageRequest` ha il solo campo `text`, con `max_length` che fa respingere dalla validazione un
testo troppo lungo **prima** che il modello lo vettorizzi. `model_config = {"extra": "forbid"}`
rifiuta un corpo con campi sconosciuti invece di ignorarli in silenzio: chi scrive `txet` se lo
sente dire.

## 5. Pagina di indice

`GET /` restituisce una pagina HTML che elenca gli endpoint, i codici di esito e un esempio di
chiamata, e rimanda a `/docs` per provarla. Prima la radice rispondeva **404**, perché l'API vive
solo sui propri percorsi: chi apriva l'indirizzo in un browser non trovava nulla.

L'indirizzo nell'esempio `curl` viene da `request.base_url` e non da una costante, **perché un
deploy serverless riceve un URL nuovo ogni volta** e uno scritto a mano invecchierebbe al primo
rilascio. La pagina è HTML in una stringa, senza motore di template: è l'unica del servizio, e
Jinja sarebbe una dipendenza per lei sola.

## 6. Richieste respinte e endpoint

Un corpo che Pydantic rifiuta non raggiunge mai la funzione dell'endpoint, quindi nella versione
locale **non lasciava alcuna traccia**: il registro documentava tutte le chiamate tranne proprio
quelle malformate. Un handler su `RequestValidationError` le registra e poi delega la risposta a
`request_validation_exception_handler`, così il corpo dell'errore resta quello standard.

| esito | codice | quando |
| --- | --- | --- |
| lingua riconosciuta | 200 | `{"language_code": "IT", "confidence": 1.0}` |
| testo vuoto | 400 | richiesta mal composta, responsabilità del chiamante |
| lingua non identificata | 409 | ben formata ma non lavorabile |
| corpo non valido | 422 | malformato, campo sconosciuto, o testo troppo lungo |

Il **409 al posto del 422** della versione locale è la correzione che rende i tre casi
distinguibili: prima la confidenza bassa e il corpo malformato arrivavano con lo stesso numero, e
si separavano solo guardando la forma di `detail`.

---

## Note di progetto — scelte e limiti dichiarati

1. **Modello caricato nel lifespan**, una volta per istanza invece che a ogni richiesta, con
   l'errore che emerge all'avvio. Limite noto: il costo si ripaga a ogni avvio a freddo.
2. **Percorso da `__file__`**, che toglie il vincolo su da dove si lancia il programma.
3. **Registro su standard output**, unica via su un filesystem non scrivibile. Limite noto: la
   conservazione è di un'ora sul piano gratuito, e le righe sono contate, 256 per richiesta.
4. **Richieste respinte registrate da un handler dedicato**, altrimenti invisibili al registro.
5. **409 per la lingua non identificata**, che lascia 422 alla sola validazione.
6. **Soglia a 0,5**: con tre lingue la vincente deve valere più delle altre due insieme. Limite
   noto, e va detto perché chi legge la risposta non può dedurlo: **la soglia non intercetta gli
   errori del modello**. Una frase in spagnolo riceve comunque una delle tre risposte, e con
   piena sicurezza — misurato, «Estatua de marmol de un emperador romano del siglo primero.»
   esce come IT con confidenza 1,0.
7. **`scikit-learn` fissato a 1.6.0 con `==`**, la versione con cui il `.pkl` è stato prodotto:
   aprirlo con un'altra emette `InconsistentVersionWarning`.
8. **Lunghezza massima nello schema**, che protegge il tempo di calcolo. Limite noto: la
   piattaforma impone comunque un proprio limite sul corpo, molto più alto.
9. **Endpoint pubblico, senza chiave.** Limite noto: chiunque ne conosca l'indirizzo può
   consumarne il tempo di calcolo. Finché espone solo la lingua di un testo che il chiamante già
   possiede non diffonde nulla di riservato, ma prima di un uso reale va messo dietro una chiave.
10. **`/health` e `/` aggiunti oltre la traccia**: il primo distingue un servizio avviato da uno
    che sta ancora caricando senza pagare una previsione, la seconda evita il 404 sulla radice.
    Limite noto: `/health` dice che il modello è in memoria, non che predice bene; la pagina di
    indice va aggiornata a mano se cambiano gli endpoint, mentre `/docs` nasce dagli schemi.

## Sviluppi futuri

1. Endpoint per lotti di testi, per un'intera sala in una chiamata: il modello lavora già su
   liste, ma il formato della risposta va concordato con chi chiama.
2. Chiave API e limitazione della frequenza, necessarie appena il servizio smette di essere una
   dimostrazione.
3. Raccolta dei log verso un servizio esterno, perché valgano come audit a distanza di mesi e non
   di ore.
4. Ricalibrazione della confidenza su un insieme di validazione, così che il numero sia una
   probabilità leggibile e non solo un ordinamento.
5. Una classe di rifiuto per le lingue non note, oggi impossibile: il modello sceglie sempre fra
   tre. È lavoro sul modello, non sul servizio.
