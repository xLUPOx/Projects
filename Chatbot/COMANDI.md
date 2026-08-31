# Comandi

Assistente del catasto del verde. Contesto e scelte progettuali: [PROGETTO.md](PROGETTO.md).

---

## A. Creare il progetto da zero

### Backend

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install fastapi "uvicorn[standard]" pydantic google-genai python-dotenv numpy python-dateutil snowballstemmer rank_bm25 geographiclib geographiclib
pip freeze > backend\requirements.txt
```

La chiave va in `backend\.env`:

```powershell
copy backend\.env.example backend\.env
```

```ini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.6-flash
EMBEDDING_MODEL=gemini-embedding-001
```

Se hai più chiavi, mettile tutte su una riga sola separate da virgola: quando
una tocca il limite lo stream passa alla successiva invece di aspettare.

```ini
GEMINI_API_KEYS=chiave1,chiave2,chiave3,chiave4,chiave5
```

**Devono stare su progetti Google diversi.** Le quote del free tier si contano
per progetto, non per chiave: cinque chiavi dello stesso progetto pescano dallo
stesso secchio e non cambia niente. `GET /api/health` dice quante ne sono
caricate, quante utilizzabili e quante ferme in questo momento.

Genera il catasto alberi finto (stessi parametri, stesso file):

```powershell
python backend\seed_data.py
python backend\seed_data.py --seed 42 --epoca 2027-01-15   # un altro catasto
```

Seed ed epoca finiscono dentro il GeoJSON: il primo decide *quali* alberi
escono, la seconda *rispetto a quando* sono datate le ispezioni, e il catasto
rilegge quest'ultima come "oggi" invece di usare la data di sistema.
Cambiandoli vanno riscritti i tre conteggi in `DEMO_FACTS`, in cima a
`backend/test_cadastre.py`: sono l'unico posto in cui stanno, e i test dicono
esattamente quali.

### Frontend

Angular 20 e non l'ultima versione: la CLI più recente richiede Node >= 22.22,
qui Node è 22.19. Controlla con `node -v`.

```powershell
npx @angular/cli@20 new frontend --style=css --ssr=false --skip-git --package-manager=npm --defaults
cd Chatbot
cd frontend
npm install leaflet @types/leaflet
```

In `angular.json`, dentro `architect > build > options`:

```json
"styles": ["node_modules/leaflet/dist/leaflet.css", "src/styles.css"],
"allowedCommonJsDependencies": ["leaflet"]
```

---

## B. Avviare (ogni volta)

Servono due terminali. Il backend sta sulla **8000**, il frontend sulla **4200**.

### Terminale 1 — backend

```powershell
.\venv\Scripts\Activate.ps1
cd Chatbot
cd backend
python -m uvicorn main:app --reload
```

| URL | Cosa mostra |
|---|---|
| http://127.0.0.1:8000/docs | Swagger degli endpoint |
| http://127.0.0.1:8000/api/health | Se il RAG usa embedding o BM25, quanti alberi sono caricati, e come stanno le chiavi |

### Controllare le chiavi API

Da un terminale qualsiasi, con il backend acceso — non serve fermarlo:

```powershell
(Invoke-RestMethod http://127.0.0.1:8000/api/health).keys
```

```
total usable exhausted
----- ------ ---------
    4      4         0
```

In PowerShell scrivi `curl.exe`, non `curl`: `curl` è un alias di
`Invoke-WebRequest` e con `-s` dà errore.

| Campo | Cosa dice |
|---|---|
| `total` | quante chiavi ha letto da `GEMINI_API_KEYS` |
| `usable` | quante sono spendibili **adesso** |
| `exhausted` | quante hanno finito la quota **giornaliera** |

`usable` non è `total - exhausted`, e la differenza conta durante una demo. Gli
stop sono due: il limite **al minuto** mette la chiave in pausa per qualche
decina di secondi, quello **giornaliero** la toglie dal giro. Una chiave in
pausa breve sparisce da `usable` senza comparire in `exhausted`: `usable: 2,
exhausted: 0` su 4 chiavi significa che due rientrano da sole entro un minuto,
non che le hai perse.

Anche `exhausted` si riassorbe: sono le chiavi esaurite *adesso*, riprovate
dopo mezz'ora, perché le quote di Google si azzerano a mezzanotte del fuso
Pacifico e una chiave già riabilitata non deve restare fuori.

*Quale* chiave sia esaurita l'endpoint non lo dice, di proposito: non è
autenticato, e stampare pezzi di chiave in una risposta HTTP è il modo classico
per farle finire in un log. Se serve saperlo, il warning della rotazione è nei
log di uvicorn.

### Terminale 2 — frontend

```powershell
cd Chatbot
cd frontend
npm start
```

http://localhost:4200/

### Se qualcosa non parte

| Sintomo | Causa | Rimedio |
| --- | --- | --- |
| `npm start` → `Missing script: start` | lanciato dalla cartella sbagliata | `cd frontend` prima |
| `npm start` → `Port 4200 is already in use` | un dev server è rimasto acceso | chiudi il terminale che lo teneva |
| La pagina dice che su 8000 risponde un'altra applicazione | un altro progetto di `intervista` occupa la porta | chiudi quel terminale, oppure avvia questo backend con `--port 8001` e apri `http://localhost:4200/?api=8001` |
| La pagina dice che manca `GEMINI_API_KEY` | `backend\.env` assente o vuoto | crealo da `.env.example` e riavvia uvicorn |

---

## C. Test

Offline, senza API key, deterministici — sessantaquattro in tutto:

```powershell
cd backend
python test_cadastre.py     # 22 - catasto, query spaziali, statistiche
python test_agent.py        # 15 - ciclo dell'agente con un modello finto
python test_quota.py        # 12 - 429, e rotazione fra più chiavi
python test_rag.py          #  6 - chunking, recupero, soglia
python test_citations.py    #  6 - in "Fonti" solo cio' che e' citato
python test_api.py          #  3 - endpoint e lifespan
```

`test_agent.py` sostituisce solo `generate_content_stream` con chunk finti:
turni, dispatch dei tool, errori che rientrano nel contesto e tetto sui giri
sono verificati senza chiave e senza rete.

`test_rag.py` gira in modalità BM25 (rimuove la `GEMINI_API_KEY`): copre il
chunking, il recupero e la soglia lessicale, non il ramo con gli embedding.

Frontend — sette test su `segment()`, l'unico punto con logica propria:

```powershell
cd frontend
npm test
```

Suite di regressione sull'agente — questa chiama davvero il modello:

```powershell
python eval\run.py                 # tutti i casi
python eval\run.py rule            # solo i casi il cui nome contiene "rule"
```

Senza `GEMINI_API_KEY` si ferma subito invece di far fallire dieci casi con
lo stesso errore.

Il free tier concede 5 richieste al minuto e ogni caso ne consuma 2-3: fra un
caso e l'altro la suite aspetta 45 secondi, quindi il giro completo dura circa
otto minuti. Se compaiono errori 429, alza la pausa:

```powershell
$env:EVAL_PAUSE_S = 60
python eval\run.py
```

---

## D. Demo — cinque domande in difficoltà crescente

1. Quanti tigli ci sono nel quartiere Gries?
2. Alberi a rischio moderato o elevato non ispezionati da almeno 24 mesi entro 400 m dalla Scuola Primaria Gries
3. Ogni quanto va potato un platano secondo il regolamento?
4. Plottami gli alberi della zona più centrale della città per categoria a,b,c,d — **il grafico lo disegna l'interfaccia, e la mappa illumina gli stessi alberi**
5. Qual è il valore economico stimato degli alberi di Oltrisarco? — **deve rispondere che il dato non c'è**

La quinta è la più importante: è quella che dimostra che le prime quattro sono affidabili.

La quarta è l'unica in cui il modello non riceve un nome di quartiere: «la zona
più centrale della città» lo obbliga a passare da `allowed_values` per scoprire
che si chiama Centro-Piani-Rencio. È anche l'unica che esercita il grafico.

**Da provare a mano prima della demo:** una domanda di seguito ("e quelli in
classe C?") dopo la prima. La conversazione precedente viaggia nel corpo della
richiesta e `_history_to_contents` ne tiene gli ultimi otto messaggi; il
formato è coperto da `test_agent.py`, ma se il *modello* usa male il contesto
lo si vede solo provando. Non è un caso della suite eval apposta: aggiungerlo
costerebbe altri 45 secondi di attesa a ogni giro.
