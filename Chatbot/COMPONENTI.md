# Progetto
un assistente del catasto del verde. Domanda in italiano → l'agente sceglie fra cinque tool → 
risponde citando le fonti → la mappa accende gli alberi citati. Due metà: `backend/` è il ciclo 
dell'agente, `frontend/src/app/` è il prodotto.
Ogni voce chiude col verdetto — **la
rifarei** in produzione, oppure **è da MVP** e allora cosa cambierei.

## Backend

- **[main.py](backend/main.py)** — FastAPI, endpoint e ciclo dell'agente.
  *E non Flask:* i contratti Pydantic sono già validazione e già Swagger, e
  l'async serve: la risposta è uno stream. **La rifarei** — è il default per
  un'API tipizzata, non una comodità.
- **SSE e non WebSocket.** Il flusso va in un verso solo. **La rifarei;**
  cambierei solo con un canale bidirezionale — interrompere una risposta, più
  utenti sulla stessa sessione.
- **[tools.py](backend/tools.py)** — le cinque funzioni che il modello può
  chiedere. *E non text-to-SQL:* il modello sceglie *quale* funzione e con
  quali argomenti, cosa può fare lo decido io. **La rifarei: è il confine di
  sicurezza, non una scorciatoia da MVP.** Il prezzo lo dico — text-to-SQL
  risponde anche a domande che non ho previsto, i miei tool no. Su dati di
  sicurezza pubblica una superficie stretta vale più della copertura.
- **[cadastre.py](backend/cadastre.py)** — SQLite in memoria, distanza
  geodetica dopo un prefiltro a bounding box. *E non embedding:* un conteggio
  dev'essere esatto, non simile, e vale a ogni scala. *E non una haversine
  scritta a mano,* che stava qui prima: `geographiclib` è l'implementazione di
  riferimento di Karney sull'ellissoide WGS-84, cioè la stessa matematica che
  PROJ porta dentro PostGIS. **La rifarei: il numero è già quello di
  produzione.** **Da MVP resta l'accesso:** nessun indice spaziale, quindi il
  prefiltro è una scansione. `ST_DWithin` e GiST cambiano il corpo della
  funzione, non la firma del tool.
- **[rag.py](backend/rag.py)** — embedding Gemini, coseno con numpy, fallback
  BM25. *E non FAISS o pgvector:* undici articoli stanno in una matrice.
  **Giusta a questa scala, e la scala è il criterio:** la forza bruta regge fino
  a qualche decina di migliaia di vettori. Oltre, pgvector — non FAISS: il
  Postgres in produzione c'è già, e un servizio in meno è un servizio in meno.
- **[eval/](backend/eval/)** — undici casi, quattro verificano che l'agente
  **rifiuti**. *Separata dai test unitari,* che girano senza rete con un modello
  finto ([test_agent.py](backend/tests/test_agent.py)): qui invece si chiama Gemini
  davvero, un caso morto sul rate limit va marcato `SKIP` e non `FAIL`, e il
  giudizio è per parola intera, non per sottostringa.
  **La separazione la rifarei, la suite è incompleta:** non gira in CI e non
  misura recupero, costo e latenza separatamente.

## Frontend

- **Angular 20, standalone e signals.** *E non React,* che avevo già pronto.
  **Qui sono onesto: non è una scelta tecnica, è una scelta di contesto.**
  React sarebbe stato più veloce a parità di risultato; Angular è il primo dei
  vostri "preferred", e scriverlo vale più del dichiararlo.
- **[state.ts](frontend/src/app/state.ts)** — signals condivisi fra chat
  e mappa. *E non NgRx:* lo stato è una manciata di segnali e la reattività
  granulare la dà già il framework. **La rifarei a questa dimensione;** uno
  store con più feature che scrivono lo stesso stato, o dovendo tracciare chi
  l'ha cambiato.
- **[api.ts](frontend/src/app/api.ts)** — lettura dello stream a mano.
  *E non `EventSource`,* che non fa POST. *E nemmeno una libreria SSE:* provata
  e tolta, perché le sue due funzioni utili — riconnessione e chiusura a scheda
  nascosta — qui vanno spente (riconnettersi rifà la POST, cioè riesegue
  l'agente), e senza quelle resta il parsing di un formato che il mio server
  emette in una forma sola. **La rifarei a mano:** è l'unico punto del progetto
  dove ho preso una libreria e poi l'ho restituita.
- **[map.ts](frontend/src/app/map.ts)** — Leaflet diretto, senza wrapper.
  **La rifarei per centoquaranta punti:** zero token, zero servizio esterno, e
  il ciclo di vita lo governano gli `effect`. **Sul catasto vero cambierei:**
  decine di migliaia di alberi vogliono vector tile e MapLibre GL, non marker
  nel DOM.
- **[chart.ts](frontend/src/app/chart.ts)** — barre disegnate a mano.
  *E non Chart.js:* una libreria porta una palette da combattere, e qui il
  colore è dato — le quattro classi di rischio. **Giusta per una forma sola:**
  alla seconda serve una libreria, non altre barre a mano.
- **[chip.ts](frontend/src/app/chip.ts)** — la targhetta cliccabile.
  Nessuna alternativa da scartare: è l'elemento firma. Una frase senza
  targhetta non ha fonte.

## Dipendenze esterne — a cosa servono

- **fastapi** — framework web, definisce gli endpoint.
- **fastapi.middleware.cors** — permette al frontend (4200) di chiamare il backend (8000).
- **fastapi.responses.StreamingResponse** — manda la risposta a pezzi invece che tutta insieme.
- **fastapi.testclient** — chiama gli endpoint nei test senza un server acceso davvero.
- **pydantic.BaseModel** — valida forma e tipi delle richieste JSON in arrivo.
- **google.genai** — SDK ufficiale per parlare con Gemini.
- **google.genai.types / errors** — i tipi di dato (Content, Part, FunctionCall) e gli errori dell'SDK.
- **dotenv.load_dotenv** — legge la chiave API dal file `.env`.
- **numpy** — calcolo vettoriale, il coseno fra embedding nel RAG.
- **rank_bm25.BM25Okapi** — motore di ricerca testuale, fallback quando manca la chiave.
- **snowballstemmer** — riduce le parole alla radice per il matching testuale.
- **geographiclib.Geodesic** — distanza reale sull'ellissoide, non in linea d'aria approssimata.
- **dateutil.relativedelta** — differenze di mesi/anni fra date, calcolate correttamente.
- **sqlite3** — il database in memoria del catasto.
- **difflib** — corrispondenze approssimate, tollera un refuso nel nome di un luogo.
- **contextlib.asynccontextmanager** — gestisce avvio e spegnimento dell'app (`lifespan`).
- **typing** (`Any`, `Iterator`, `AsyncIterator`) — solo annotazioni di tipo, zero effetto a runtime.
- **collections.Counter** — conta occorrenze, usato per raggruppare negli aggregati.
- **pathlib.Path** — percorsi di file indipendenti dal sistema operativo.
- **datetime / date / timedelta** — gestione di date e durate.
- **json, re, os, sys, time, math, random, logging, argparse** — libreria standard: parsing JSON, regex, ambiente, percorsi, tempo, matematica, seed, log, argomenti da riga di comando.
