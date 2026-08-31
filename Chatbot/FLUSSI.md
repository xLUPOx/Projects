# Flussi — come funziona, dall'inizio alla fine

Diagrammi del funzionamento end-to-end. Contesto e scelte progettuali stanno in
[PROGETTO.md](PROGETTO.md); i comandi in [COMANDI.md](COMANDI.md).

**Legenda dei colori**, uguale in tutti i diagrammi:

| Colore | Cosa rappresenta |
|---|---|
| 🟩 verde | backend Python |
| 🟦 azzurro | frontend Angular |
| 🟨 ocra | dati a riposo (file, SQLite, indici) |
| 🟪 viola | il modello Gemini — l'unico pezzo non deterministico |
| 🟥 rosso | percorsi di errore, rifiuto, fallback |
| ⬜ grigio | decisioni |

---

## 1. Mappa generale

Tre processi. Il browser non parla mai con Gemini: la chiave sta solo nel backend,
e il modello non tocca mai il database — vede solo cinque funzioni.

```mermaid
flowchart LR
    subgraph FE["🟦 Browser — Angular 20, porta 4200"]
        direction TB
        UI["chat.html + app.html<br/>conversazione, targhette, fonti"]
        MAP["map.ts<br/>Leaflet, 140 punti"]
        CHART["chart.ts<br/>barre di sintesi"]
        STATE["state.ts<br/>signals condivisi"]
        APICL["api.ts<br/>fetch + lettura SSE"]
        UI --- STATE
        MAP --- STATE
        CHART --- STATE
        STATE --- APICL
    end

    subgraph BE["🟩 Backend — FastAPI + uvicorn, porta 8000"]
        direction TB
        MAIN["main.py<br/>endpoint e ciclo dell'agente"]
        TOOLS["tools.py<br/>i 5 tool"]
        CAD["cadastre.py<br/>SQL + geometria"]
        RAG["rag.py<br/>retriever"]
        MAIN --> TOOLS
        TOOLS --> CAD
        TOOLS --> RAG
    end

    subgraph DATA["🟨 Dati"]
        direction TB
        GEO["trees.geojson<br/>140 alberi"]
        PLACES["places.json<br/>6 luoghi"]
        REG["regolamento_verde.md<br/>11 articoli"]
    end

    GEM["🟪 Gemini<br/>generazione + embedding"]

    APICL -->|"HTTP + SSE"| MAIN
    CAD --> GEO
    CAD --> PLACES
    RAG --> REG
    MAIN <-->|"stream + function calling"| GEM
    RAG -->|"solo embedding"| GEM

    classDef fe fill:#dce9f0,stroke:#2b5f7a,stroke-width:1px,color:#12232b
    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dt fill:#f4e9c8,stroke:#8a6f07,stroke-width:1px,color:#2b2410
    classDef ai fill:#e6dcf0,stroke:#5b3f86,stroke-width:1px,color:#241833

    class UI,MAP,CHART,STATE,APICL fe
    class MAIN,TOOLS,CAD,RAG be
    class GEO,PLACES,REG dt
    class GEM ai
```

---

## 2. Avvio del backend — `lifespan`

Tutto il caricamento avviene una volta sola, all'avvio del processo. Il punto
importante è il bivio in fondo: se manca la chiave o l'API fallisce, il retriever
**non si rompe**, scende su BM25. È quello che rende i test eseguibili offline.

```mermaid
flowchart TB
    START(["uvicorn avvia l'app"]) --> LS["lifespan → startup()<br/>main.py"]

    LS --> C1["cadastre.initialize()"]
    subgraph CAD["🟩 cadastre.py"]
        direction TB
        C1 --> C2["CREATE TABLE trees<br/>tipi espliciti: REAL, INTEGER,<br/>date TEXT per l'ordinamento ISO"]
        C2 --> C3["legge trees.geojson<br/>e fa INSERT di 140 righe"]
        C3 --> C4["legge places.json<br/>6 luoghi di riferimento"]
    end

    LS --> R1["rag.initialize()"]
    subgraph RAGS["🟩 rag.py"]
        direction TB
        R1 --> R2["_split_into_articles()<br/>ogni '## Art. N' = 1 chunk"]
        R2 --> R3["_tokenize()<br/>stopword + Snowball italiano"]
        R3 --> R4["BM25Okapi(k1=1.5, b=0.75)<br/>indice lessicale sempre costruito"]
        R4 --> R5{"GEMINI_API_KEY<br/>presente?"}
        R5 -->|"sì"| R6["embed_content sugli 11 chunk"]
        R6 --> R7{"l'API<br/>ha risposto?"}
        R7 -->|"sì"| R8["_normalize()<br/>matrice 11 × 3072, righe a norma 1"]
        R7 -->|"no"| R9["🟥 log e fallback"]
        R5 -->|"no"| R9
    end

    R8 --> MODE1["modalità = 'embedding Gemini'"]
    R9 --> MODE2["🟥 modalità = 'BM25 lessicale'"]

    C4 --> READY
    MODE1 --> READY
    MODE2 --> READY
    READY(["pronto — /api/health dice quale modalità è attiva"])

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019
    classDef ok fill:#d8eadf,stroke:#2f7d52,stroke-width:1px,color:#12301f

    class LS,C1,C2,C3,C4,R1,R2,R3,R4,R6,R8 be
    class R5,R7 dec
    class R9,MODE2 err
    class MODE1 ok
```

---

## 3. Avvio del frontend — perché il controllo di salute viene prima

`state.load()` non scarica i dati e basta: prima chiede *chi* risponde su quella
porta. Senza il controllo, un altro progetto in ascolto sulla 8000 produce errori
incomprensibili invece di dire qual è il problema.

```mermaid
flowchart TB
    BOOT(["App.ngOnInit → state.load()"]) --> HC["api.check()<br/>GET /api/health"]

    HC --> D1{"la fetch<br/>è andata?"}
    D1 -->|"no"| E1["🟥 'Backend non raggiungibile su …<br/>Avvia uvicorn'"]

    D1 -->|"sì"| D2{"la risposta contiene<br/>trees_loaded?"}
    D2 -->|"no"| E2["🟥 'Su questa porta risponde<br/>un'altra applicazione'<br/>→ suggerisce ?api=8001"]

    D2 -->|"sì"| D3{"llm_configured<br/>è true?"}
    D3 -->|"no"| E3["🟥 'Manca GEMINI_API_KEY:<br/>crea backend/.env'"]

    D3 -->|"sì"| LOAD["Promise.all<br/>GET /api/cadastre + GET /api/places"]
    LOAD --> SIG["state.cadastre.set(...)<br/>state.places.set(...)"]
    SIG --> DRAW["l'effect in map.ts disegna<br/>140 cerchi + 6 segnaposto"]
    DRAW --> DONE(["interfaccia pronta"])

    E1 --> BANNER["🟥 banner in testata,<br/>casella disabilitata"]
    E2 --> BANNER
    E3 --> BANNER

    classDef fe fill:#dce9f0,stroke:#2b5f7a,stroke-width:1px,color:#12232b
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019

    class HC,LOAD,SIG,DRAW fe
    class D1,D2,D3 dec
    class E1,E2,E3,BANNER err
```

---

## 4. Una domanda, dall'inizio alla fine

È il diagramma centrale. Da notare tre cose: il ciclo dell'agente lo guidiamo
noi (AFC disabilitata), ogni chiamata a un tool produce **due** eventi in chat
(prima l'intenzione, poi l'esito), e le citazioni si calcolano **dopo** che il
testo è completo — perché solo allora si sa quali articoli il modello ha citato
davvero.

```mermaid
sequenceDiagram
    autonumber
    actor U as 🟦 Utente
    participant CT as 🟦 chat.ts
    participant ST as 🟦 state.ts
    participant AP as 🟦 api.ts
    participant MN as 🟩 main.py
    participant TL as 🟩 tools.py
    participant DS as 🟨 cadastre / rag
    participant GM as 🟪 Gemini

    U->>CT: scrive e preme Invio
    CT->>ST: ask(question)

    rect rgb(220, 233, 240)
    ST->>ST: appende 2 messaggi (utente + assistente vuoto)
    ST->>ST: azzera evidenziati e selezione
    ST->>AP: chat(question, history, AbortSignal)
    AP->>MN: POST /api/chat
    end

    rect rgb(223, 234, 228)
    MN->>MN: _history_to_contents (ultimi 8 messaggi)
    MN->>MN: config: 5 tool + AFC disabilitata + INSTRUCTIONS
    end

    loop fino a 6 turni (MAX_AGENT_TURNS)
        MN->>GM: generate_content_stream
        activate GM

        alt il modello produce testo
            GM-->>MN: chunk di testo
            MN-->>AP: SSE type=text, delta
            AP-->>ST: accumula sul messaggio
            ST-->>U: la risposta appare mentre nasce
        end

        alt il modello chiede un tool
            GM-->>MN: function_call(name, args)
            deactivate GM
            MN-->>AP: SSE type=status (nome + argomenti in chiaro)
            AP-->>U: "Interrogo il catasto alberi — quartiere: Gries"

            rect rgb(244, 233, 200)
            MN->>TL: function(**args)
            TL->>DS: search / search_near / stats / rag.search / registry
            DS-->>TL: dict di dati grezzi
            TL-->>MN: risultato
            end

            MN-->>AP: SSE type=tool (sintesi: "6 alberi corrispondenti")
            MN->>GM: Part.from_function_response — il risultato torna nel contesto
        else nessuna chiamata
            MN->>MN: esce dal ciclo
        end
    end

    rect rgb(223, 234, 228)
    MN->>MN: _collect_references(risultati, testo_finale)
    Note over MN: alberi → tutti<br/>articoli → solo quelli citati nel testo<br/>chart → solo se è stato usato cadastre_stats
    MN-->>AP: SSE type=end (trees, articles, chart, tools_used)
    end

    AP-->>ST: evento end
    ST->>ST: highlighted = id degli alberi citati
    ST-->>U: 🟦 mappa: i citati restano accesi, gli altri sbiadiscono
    ST-->>U: 🟦 chat: riga "Fonti" con le targhette cliccabili
```

---

## 5. Il dispatch dei tool

Il modello non conosce SQL né il regolamento: conosce cinque firme di funzione,
costruite da Gemini leggendo **type hint e docstring** di `tools.py`. La docstring
lì è interfaccia, non commento.

```mermaid
flowchart LR
    FC["🟪 function_call<br/>name + args"] --> LOOKUP{"TOOLS.get(name)"}

    LOOKUP -->|"non trovato"| UNK["🟥 {error: 'Tool sconosciuto'}<br/>rimandato al modello"]
    LOOKUP -->|"trovato"| CALL{"function(**args)<br/>solleva TypeError?"}
    CALL -->|"sì"| TE["🟥 {error: 'Argomenti non validi'}<br/>il modello di solito ritenta correggendosi"]

    CALL -->|"no"| T1["search_trees"]
    CALL --> T2["search_trees_near"]
    CALL --> T3["cadastre_stats"]
    CALL --> T4["consult_regulation"]
    CALL --> T5["allowed_values"]

    T1 --> S1["cadastre.search<br/>SELECT con WHERE dinamico"]
    T2 --> S2["cadastre.search_near<br/>bounding box + geodetica"]
    T3 --> S3["cadastre.stats<br/>GROUP BY, o conteggio sul sottoinsieme spaziale"]
    T4 --> S4["rag.search<br/>coseno o BM25 + soglia"]
    T5 --> S5["cadastre.registry<br/>vocabolario reale dei dati"]

    S1 --> OUT["dict con gli id degli alberi<br/>o i riferimenti degli articoli"]
    S2 --> OUT
    S3 --> OUT
    S4 --> OUT
    S5 --> OUT
    OUT --> BACK["🟪 torna al modello<br/>+ 🟦 evento SSE per l'interfaccia"]

    classDef ai fill:#e6dcf0,stroke:#5b3f86,stroke-width:1px,color:#241833
    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019

    class FC,BACK ai
    class T1,T2,T3,T4,T5,S1,S2,S3,S4,S5,OUT be
    class LOOKUP,CALL dec
    class UNK,TE err
```

**Perché il vocabolario è un tool.** `allowed_values` esiste perché il modello,
davanti a un quartiere che non riconosce, ha due strade: indovinare o chiedere.
La regola 6 del prompt gli dice di chiedere, e questo tool è la risposta.

---

## 6. Il RAG, dal documento alla citazione

Due retriever dietro la stessa firma. La parte che conta non è il recupero: è la
**soglia assoluta**, che permette di non restituire niente.

```mermaid
flowchart TB
    Q["domanda riformulata<br/>dal modello"] --> MODE{"i vettori<br/>sono caricati?"}

    MODE -->|"sì"| E1["embedding della domanda"]
    E1 --> E2["_similarity()<br/>matrice @ vettore — un solo prodotto"]
    E2 --> TH1["soglia = 0.55<br/>COSINE_THRESHOLD"]

    MODE -->|"no"| B1["🟥 _tokenize() + BM25Okapi.get_scores()"]
    B1 --> TH2["soglia = 2.0<br/>BM25_THRESHOLD"]

    TH1 --> RANK["ordina, prende i primi 3"]
    TH2 --> RANK

    RANK --> CUT{"punteggio ≥ soglia?"}
    CUT -->|"no"| NONE["🟥 found = 0<br/>notice: 'Nessun articolo pertinente'"]
    CUT -->|"sì"| KEEP["articoli con reference, title,<br/>text, source, relevance"]

    NONE --> SAY["🟥 il modello dice<br/>'il regolamento non lo prevede'"]
    KEEP --> CITE["il modello cita 'Art. 10'<br/>nel testo della risposta"]

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019
    classDef ok fill:#d8eadf,stroke:#2f7d52,stroke-width:1px,color:#12301f

    class Q,E1,E2,TH1,B1,TH2,RANK be
    class MODE,CUT dec
    class NONE,SAY err
    class KEEP,CITE ok
```

**Le soglie sono assolute, non relative al miglior risultato.** Normalizzando sul
massimo, il migliore vale sempre 1 e il sistema cita comunque l'articolo meno
peggio. Le due scale sono diverse, quindi le soglie sono due.

### Perché lo stemming conta

```mermaid
flowchart LR
    A["'quando si può<br/>abbattere un albero?'"] --> B["stopword via:<br/>quando, si, può, un"]
    B --> C["Snowball italiano"]
    C --> D["abbattere → abbatt<br/>albero → alber"]
    D --> E["🟨 indice: 'Art. 14 — Abbattimento'<br/>abbattimento → abbatt ✓"]

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dt fill:#f4e9c8,stroke:#8a6f07,stroke-width:1px,color:#2b2410
    class A,B,C,D be
    class E dt
```

`STOP_WORDS` contiene anche `comunale`: non è una stopword dell'italiano, è una
stopword **di questo corpus**. Tutto il documento è il regolamento di un comune,
quindi quella parola non distingue un articolo dall'altro — e senza toglierla
*"gli orari della biblioteca comunale"* pescava l'Art. 1 e superava la soglia.

---

## 7. La query spaziale

Due stadi. Il primo è solo un'ottimizzazione, il secondo è la verità. L'invariante
del prefiltro è che non deve **mai** escludere un albero che la distanza esatta
accetterebbe — per questo usa il grado di latitudine al suo minimo (110 574 m) e
non quello medio.

```mermaid
flowchart TB
    IN["search_near('Scuola Primaria Gries', 400 m)"] --> FIND["_find_place — tre stadi"]

    subgraph FP["🟩 risoluzione del luogo"]
        direction TB
        F1["1. sottostringa esatta"] -->|"niente"| F2["2. match per parola > 3 lettere"]
        F2 -->|"niente"| F3["3. difflib, cutoff 0.6<br/>regge i refusi: 'Primara Gris'"]
    end

    FIND --> FP
    F3 -->|"niente"| ERR["🟥 error + available_places<br/>il modello può riprovare con un nome valido"]

    F1 --> BOX
    F2 --> BOX
    F3 --> BOX
    BOX["_degree_deltas(lat, 400)<br/>semiampiezze in gradi"]

    BOX --> SQL["🟨 SELECT … WHERE<br/>lat BETWEEN ? AND ?<br/>lng BETWEEN ? AND ?"]
    SQL --> CAND["candidati — pochi, non 140"]
    CAND --> HAV["distance_m() su ognuno<br/>geodetica WGS-84, geographiclib"]
    HAV --> FILT{"d ≤ 400 m?"}
    FILT -->|"no"| DROP["scartato"]
    FILT -->|"sì"| KEEP["albero + distance_m arrotondata"]
    KEEP --> SORT["ordina per distanza crescente"]

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dt fill:#f4e9c8,stroke:#8a6f07,stroke-width:1px,color:#2b2410
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019

    class IN,FIND,F1,F2,F3,BOX,CAND,HAV,KEEP,SORT be
    class SQL dt
    class FILT dec
    class ERR err
```

In produzione questo strato diventa PostGIS `ST_DWithin` senza toccare la firma
dei tool: il modello non se ne accorgerebbe.

---

## 8. Il filtro delle citazioni

Alberi e articoli seguono due regole **diverse**, e la differenza è deliberata.

```mermaid
flowchart TB
    IN["risultati dei tool + testo finale"] --> SPLIT{"che tipo<br/>di risultato?"}

    SPLIT -->|"trees[]"| TREE["🟩 entrano tutti nelle fonti"]
    TREE --> WHY1["sono comunque evidenziati sulla mappa:<br/>la targhetta rimanda a qualcosa"]

    SPLIT -->|"articles[]"| ART{"_article_cited(reference, testo)<br/>regex \\bart(\\.|icolo)?\\s*N\\b"}
    ART -->|"no"| DROP["🟥 scartato — è solo un residuo della ricerca"]
    ART -->|"sì"| KEEP["🟩 entra nelle fonti"]

    SPLIT -->|"counts[] da cadastre_stats"| CHART["🟩 chart: title, subtitle, items"]

    DROP --> PACT["il patto: ogni targhetta<br/>corrisponde a un'affermazione"]
    KEEP --> PACT
    WHY1 --> PACT
    CHART --> END["evento SSE type=end"]
    PACT --> END

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019
    classDef ok fill:#d8eadf,stroke:#2f7d52,stroke-width:1px,color:#12301f

    class IN,TREE,WHY1,CHART be
    class SPLIT,ART dec
    class DROP err
    class KEEP,PACT,END ok
```

Un articolo recuperato ma non usato, mostrato fra le fonti, rompe il patto — e
insegna a non fidarsi neanche delle altre targhette. Il confine di parola nella
regex serve a non far pescare `Art. 5` da `Art. 50`.

---

## 9. I 429: due limiti che si somigliano e vanno trattati all'opposto

Gemini manda un `retryDelay` in **entrambi** i casi. Sul limite giornaliero dice
59 s, che è una promessa che non può mantenere. Il campo che li separa è il
`quotaId`.

Con più chiavi configurate (`GEMINI_API_KEYS`) la distinzione decide anche
**cosa farne della chiave**: il limite al minuto la mette in pausa, quello
giornaliero la toglie dal giro. In entrambi i casi la prima mossa non è
aspettare, è cambiare chiave — che costa zero secondi.

```mermaid
flowchart TB
    ERR["🟥 ClientError 429"] --> Q3{"avevamo già<br/>emesso chunk?"}
    Q3 -->|"sì"| RAISE["🟥 rilancia — ritentare duplicherebbe il testo"]
    Q3 -->|"no"| Q1{"il testo contiene<br/>'PerDay'?"}

    Q1 -->|"sì"| DAY["keys.mark_exhausted()<br/>fuori dal giro, risondata fra 30'"]
    Q1 -->|"no"| PAUSE["keys.mark_paused(retryDelay)<br/>torna buona da sola"]

    DAY --> Q4{"c'è un'altra<br/>chiave libera?"}
    PAUSE --> Q4
    Q4 -->|"sì"| RETRY(["ritenta subito, senza dormire"])
    Q4 -->|"no"| Q5{"keys.wait_time()"}

    Q5 -->|"secondi"| SLEEP["sleep e ritenta<br/>la demo dal vivo sopravvive"]
    Q5 -->|"None"| MSG["🟥 tutte esaurite: messaggio azionabile<br/>'attiva la fatturazione, aggiungi<br/>una chiave, o riprova domani'"]
    SLEEP --> RETRY

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dec fill:#eceee9,stroke:#7b8a83,stroke-width:1px,color:#182420
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019

    class PAUSE,DAY,SLEEP,RETRY be
    class Q1,Q3,Q4,Q5 dec
    class ERR,RAISE,MSG err
```

`wait_time()` guarda solo le pause brevi: sul limite giornaliero non si dorme
mai, perché mezz'ora di attesa e un errore, per chi ha appena fatto la domanda,
sono la stessa cosa.

La stessa distinzione serve alla suite di eval: un caso morto sulla quota non
dice **niente** sull'agente, quindi ha uno stato `SKIP` separato da `FAIL`.

---

## 10. Dallo stream SSE allo schermo

Cinque tipi di evento, ognuno con il suo effetto sull'interfaccia. Il buffer in
`api.ts` accumula finché non trova `\n\n`, perché un chunk di rete può spezzare
un JSON a metà.

```mermaid
flowchart LR
    subgraph WIRE["🟩 backend — un evento per riga data:"]
        direction TB
        EV1["type=status"]
        EV2["type=tool"]
        EV3["type=text"]
        EV4["type=end"]
        EV5["🟥 type=error"]
    end

    subgraph UIS["🟦 frontend — state.ts"]
        direction TB
        A1["appende uno Step<br/>done=false"]
        A2["closeStep: chiude il primo<br/>Step aperto con quel nome"]
        A3["message.text += delta"]
        A4["trees, articles, chart<br/>highlighted = id citati"]
        A5["🟥 message.error"]
    end

    subgraph SCREEN["🟦 cosa si vede"]
        direction TB
        V1["riga 'Interrogo il catasto —<br/>quartiere: Gries · in corso…'"]
        V2["la stessa riga si chiude:<br/>'6 alberi corrispondenti'"]
        V3["la risposta compare parola per parola"]
        V4["mappa filtrata + riga Fonti + grafico"]
        V5["🟥 banner rosso nel messaggio"]
    end

    EV1 --> A1 --> V1
    EV2 --> A2 --> V2
    EV3 --> A3 --> V3
    EV4 --> A4 --> V4
    EV5 --> A5 --> V5

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef fe fill:#dce9f0,stroke:#2b5f7a,stroke-width:1px,color:#12232b
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019

    class EV1,EV2,EV3,EV4 be
    class A1,A2,A3,A4,V1,V2,V3,V4 fe
    class EV5,A5,V5 err
```

**Perché `closeStep` cerca il primo passo aperto con quel nome:** un tool può
essere chiamato più volte nella stessa risposta, e chiudere quello sbagliato
lascia in pagina una riga "in corso…" che non finisce mai.

---

## 11. Il patto chat ↔ mappa

La risposta e le feature sulla mappa sono la stessa cosa vista due volte. Il
puntamento va nei due sensi, e passa sempre dai signal condivisi — nessun
componente parla direttamente con l'altro.

```mermaid
stateDiagram-v2
    direction LR

    [*] --> Riposo

    Riposo --> Evidenziato: arriva type=end<br/>highlighted = {ALB-0042, …}
    Evidenziato --> Riposo: nuova domanda<br/>highlighted azzerato

    state Evidenziato {
        direction LR
        [*] --> Nessuno
        Nessuno --> Sorvolato: mouse su targhetta<br/>o su punto in mappa
        Sorvolato --> Nessuno: mouse via
        Nessuno --> Selezionato: click su targhetta<br/>o su punto
        Sorvolato --> Selezionato: click
        Selezionato --> Nessuno: popup chiuso<br/>(X, Esc, click sulla mappa)
    }

    note right of Evidenziato
        Sorvolato: punto ingrandito, targhetta accesa
        Selezionato: + flyTo, popup aperto,
        quadrante in testata aggiornato
    end note
```

```mermaid
flowchart LR
    CHIP["🟦 chip.ts<br/>targhetta in chat"] -->|"click → selected.set(id)"| ST["🟦 state.ts<br/>selected · hovered · highlighted"]
    MAPC["🟦 map.ts<br/>cerchio sulla mappa"] -->|"click → selected.set(id)"| ST
    ST -->|"effect"| CHIP2["🟦 la targhetta si accende"]
    ST -->|"effect"| MAPC2["🟦 flyTo + popup + raggio 9px"]
    ST -->|"binding"| HEAD["🟦 quadrante 'Selezionato' in testata"]

    classDef fe fill:#dce9f0,stroke:#2b5f7a,stroke-width:1px,color:#12232b
    class CHIP,MAPC,ST,CHIP2,MAPC2,HEAD fe
```

Il `popupclose` di Leaflet confronta il popup che si chiude con quello
dell'albero selezionato: senza quel confronto, aprire il popup di B chiude
quello di A e la selezione di B verrebbe cancellata nell'istante in cui nasce.

---

## 12. Il modello dei dati

```mermaid
erDiagram
    TREES {
        TEXT id PK "ALB-0042"
        TEXT species "Platanus x acerifolia"
        TEXT common_name "Platano"
        TEXT district "Gries-San Quirino"
        TEXT street
        TEXT planting_date "ISO"
        REAL height_m
        INTEGER girth_cm
        TEXT risk_class "A B C D"
        TEXT health_status "Buono Discreto Scadente Critico"
        TEXT last_inspection "ISO, confronto lessicografico"
        TEXT last_pruning "ISO"
        INTEGER pruning_interval_months
        INTEGER protected
        REAL lat
        REAL lng
    }

    PLACES {
        TEXT name "Scuola Primaria Gries"
        TEXT type "scuola parco ospedale stazione"
        REAL lat
        REAL lng
    }

    CHUNKS {
        TEXT reference PK "Art. 10"
        TEXT title
        TEXT text
        TEXT source "regolamento_verde.md"
        LIST tokens "stem Snowball"
    }

    TREES ||--o{ PLACES : "distanza calcolata a runtime"
    CHUNKS ||--o{ TREES : "nessuna relazione: due domini separati"
```

**Le date restano `TEXT` di proposito.** In formato ISO si ordinano e si
confrontano lessicograficamente, che è esattamente quello che serve a
`last_inspection < ?`. Il resto ha il suo tipo, così i valori tornano già
numerici da sqlite3.

I due campi calcolati — `months_since_inspection` e `months_since_pruning` — non
stanno nel DB: li aggiunge `_row_to_dict` con `relativedelta`, che tiene conto
del giorno (fra il 31 gennaio e il 1 febbraio è passato 0, non 1).

---

## 13. Le difese contro le allucinazioni

Non si eliminano: si stratificano. Ogni strato lascia passare qualcosa, e quello
sotto lo prende.

```mermaid
flowchart TB
    Q["🟪 il modello vuole rispondere"] --> L1

    L1["1 · Ancoraggio ai tool<br/>nessun accesso libero al DB,<br/>solo 5 funzioni tipizzate"]
    L1 --> L2["2 · Istruzioni esplicite<br/>8 regole; la 2 impone di ammettere<br/>il dato mancante"]
    L2 --> L3["3 · Il RAG può dire di no<br/>soglie assolute, non relative"]
    L3 --> L4["4 · Vocabolario invece di invenzione<br/>allowed_values prima di indovinare"]
    L4 --> L5["5 · Citazioni verificate<br/>in Fonti solo gli articoli<br/>davvero citati nel testo"]
    L5 --> L6["6 · Errori parlanti<br/>luogo o campo sbagliato →<br/>il modello ritenta correggendosi"]
    L6 --> OUT["🟩 risposta con fonte<br/>oppure ammissione esplicita"]

    OUT --> EVAL["🟨 eval/run.py — 11 casi<br/>4 dei quali verificano che RIFIUTI"]

    classDef ai fill:#e6dcf0,stroke:#5b3f86,stroke-width:1px,color:#241833
    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef dt fill:#f4e9c8,stroke:#8a6f07,stroke-width:1px,color:#2b2410
    classDef ok fill:#d8eadf,stroke:#2f7d52,stroke-width:1px,color:#12301f

    class Q ai
    class L1,L2,L3,L4,L5,L6 be
    class OUT ok
    class EVAL dt
```

La quinta domanda della demo — *"qual è il valore economico degli alberi di
Oltrisarco?"* — è la più importante: è quella che dimostra che le prime quattro
sono affidabili.

---

## 14. Cosa copre quale test

```mermaid
flowchart LR
    subgraph OFF["🟩 offline — nessuna rete, deterministici"]
        direction TB
        T1["tests/test_cadastre.py — 23<br/>filtri, geometria, soglia mesi,<br/>invariante del bounding box"]
        T2["tests/test_rag.py — 6<br/>chunking, recupero, fuori dominio"]
        T3["tests/test_citations.py — 6<br/>quali fonti finiscono in interfaccia"]
        T4["tests/test_quota.py — 13<br/>429 al minuto vs giornaliero,<br/>rotazione delle chiavi"]
        T5["tests/test_api.py — 3<br/>lifespan, endpoint,<br/>proprietà del GeoJSON"]
        T6["tests/test_agent.py — 15<br/>turni, dispatch dei tool, errori,<br/>tetto sui giri — modello finto"]
        T7["format.spec.ts — 14<br/>targhette ALB- e Art.,<br/>recinti di codice"]
    end

    subgraph ON["🟪 usa davvero il modello"]
        EV["eval/run.py — 11 casi<br/>tool attesi, contenuto,<br/>tipo di citazione"]
    end

    subgraph GAP["🟥 scoperto"]
        G1["il ramo embedding di rag.py:<br/>i test tolgono la API key,<br/>quindi girano sempre in BM25.<br/>COSINE_THRESHOLD non è tarata da nessun test"]
        G2["il rendering Angular:<br/>nessun test di componente"]
    end

    T1 --> COV["🟩 strato dati e regole"]
    T2 --> COV
    T3 --> COV
    T4 --> COV
    T5 --> COV
    T7 --> COV
    T6 --> BEH["🟪 comportamento dell'agente"]
    EV --> BEH

    classDef be fill:#dfeae4,stroke:#2e5e4e,stroke-width:1px,color:#182420
    classDef ai fill:#e6dcf0,stroke:#5b3f86,stroke-width:1px,color:#241833
    classDef err fill:#f3dcdf,stroke:#93273f,stroke-width:1px,color:#3d1019

    class T1,T2,T3,T4,T5,T7,COV be
    class T6,EV,BEH ai
    class G1,G2 err
```

---

## 15. Riepilogo dei percorsi

| Domanda | Strada | Perché |
|---|---|---|
| "quanti tigli a Gries" | SQL | un conteggio deve essere esatto, non simile |
| "entro 400 m dalla scuola" | bounding box + geodetica WGS-84 | la geometria è geometria, non semantica |
| "ogni quanto si pota un platano" | embedding, o BM25 in fallback | qui la somiglianza di significato è il punto |
| "come sono distribuiti per classe" | GROUP BY + grafico disegnato dall'interfaccia | il modello non disegna, chiama `cadastre_stats` |
| "valore economico degli alberi" | nessun tool ha il dato | ammissione esplicita, nessuna citazione |
