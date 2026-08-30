# Assistente del catasto del verde — riassunto

**Struttura:** `backend/` (Python) e `frontend-verde/` (Angular).

**Caso:** R3GIS, Bolzano. Un tecnico dell'ufficio verde deve sapere quali alberi
sono a rischio, dove sono e cosa prescrive il regolamento, senza imparare una
maschera di filtri.

**Cos'è:** un assistente che interroga in linguaggio naturale un catasto alberi.
Domanda in italiano → l'agente sceglie fra cinque tool → risponde citando le fonti
→ la mappa accende esattamente gli alberi di cui ha parlato.

**Requisiti:** Python 3.14 (le annotazioni `X | None` richiedono almeno 3.10),
FastAPI, `google-genai`, numpy, `rank_bm25`, `snowballstemmer`, `geographiclib`,
`python-dateutil`. Node con Angular 20 e Leaflet. Chiave Gemini in `.env`: senza, il retriever passa a BM25
e i test unitari girano lo stesso.

**Le quattro capacità:** filtro attributivo, query spaziale, sintesi per un
grafico, RAG sul regolamento. Sotto, gli otto blocchi in cui la repo le realizza.

---

## 1. Dati

`data/trees.geojson` (140 alberi su cinque quartieri di Bolzano),
`data/places.json` (sei punti di riferimento: scuole, parco, ospedale),
`data/regolamento_verde.md` (undici articoli, il corpus del RAG).
`backend/seed_data.py` genera il catasto: `generate_trees()` estrae quartiere,
specie, classe di propensione al cedimento, stato fitosanitario e date. Seed ed
epoca sono i suoi due parametri (`--seed`, `--epoca`) e finiscono scritti dentro
il GeoJSON: il primo decide quali alberi escono, la seconda rispetto a quando
sono datate le ispezioni. La demo è riproducibile e i test asseriscono su numeri
stabili; i soli tre che dipendono dal seed stanno in `DEMO_FACTS`, in cima a
`test_cadastre.py`, scritti a mano — se li generasse il seeder, l'asserzione
confronterebbe il generatore con sé stesso.

## 2. Catasto — `backend/cadastre.py`

`initialize()` carica il GeoJSON in uno SQLite in memoria. `_where_clauses()`
costruisce i filtri una volta sola ed è condiviso da `search()`, `search_near()`
e `stats()`: le tre funzioni vedono per forza lo stesso sottoinsieme, quindi un
conteggio e il grafico che lo accompagna non possono divergere.
`distance_m()` delega a `geographiclib` la distanza geodetica sull'ellissoide
WGS-84; `_degree_deltas()` calcola il riquadro entro cui cercare, così
`search_near()` prefiltra con un `BETWEEN` su latitudine e longitudine e misura
la distanza reale solo sui candidati rimasti.
`_find_place()` risolve il nome del luogo e, se non è esatto, prova
`difflib.get_close_matches()` con soglia 0.6: tollera un refuso senza accettare
un luogo inesistente. `_months_elapsed()` traduce "non ispezionati da due anni"
in una data di taglio. `registry()` espone quartieri e specie realmente presenti
— il vocabolario che il modello può chiedere invece di indovinare.

## 3. Recupero normativo — `backend/rag.py`

`_split_into_articles()` spezza il regolamento **per articolo**, non per
lunghezza: la citazione che torna è `Art. 10`, un riferimento reale.
`initialize()` indicizza all'avvio e normalizza i vettori una volta sola, quindi
`_similarity()` è un solo prodotto matrice-vettore.
`_tokenize()` toglie le stop word e applica lo stemmer Snowball italiano, così
`abbattere` e `abbattimento` diventano lo stesso termine. `search()` applica la
soglia e può restituire **zero** articoli. Se manca la chiave, `_bm25_scores()`
subentra con `rank_bm25` Okapi, `k1=1.5` e `b=0.75` passati espliciti.

## 4. I tool — `backend/tools.py`

Le cinque funzioni che il modello può chiedere, ognuna un guscio sottile che
delega a `cadastre` o a `rag`:

- `search_trees()` — filtro attributivo su quartiere, specie, classe di
  propensione al cedimento, stato fitosanitario, tutela e mesi trascorsi
  dall'ultima ispezione → `cadastre.search()`.
- `search_trees_near()` — relazione spaziale, per le domande del tipo "vicino a",
  "entro N metri da", "attorno a" → `cadastre.search_near()`.
- `cadastre_stats()` — ripartizioni per il grafico a barre, con gli stessi filtri
  più `place_name`, così che il grafico conti gli stessi alberi elencati nel
  testo e non un insieme più ampio → `cadastre.stats()`.
- `consult_regulation()` — RAG sul regolamento del verde → `rag.search()`.
- `allowed_values()` — il vocabolario dei quartieri, delle specie, delle classi e
  dei luoghi realmente presenti nei dati → `cadastre.registry()`.


## 5. Ciclo dell'agente e streaming — `backend/main.py`

`lifespan()` inizializza catasto e indice all'avvio e fallisce lì se qualcosa
manca. `INSTRUCTIONS` sono otto regole non negoziabili: solo dati dei tool,
dichiarare il dato mancante, citare sempre la fonte, chiamare `allowed_values`
prima di indovinare, non disegnare grafici nel testo.
`_stream_agent()` guida il ciclo a mano per al massimo `MAX_AGENT_TURNS = 6`
giri: legge la `function_call`, esegue la funzione lato applicazione, rimette
l'esito nel contesto e ricomincia. Emette quattro eventi: `status` (sto per
chiamare un tool, con quali argomenti), `tool` (ha risposto), `text` (delta),
`end` (citazioni, alberi da evidenziare, grafico). La temperatura è fissata a
zero: la stessa domanda sugli stessi dati deve dare la stessa risposta.
`_article_cited()` verifica che l'articolo compaia davvero nel testo generato —
tollera `Art.10` e `articolo 10`, ma col confine di parola, per non pescare
`Art. 5` da `Art. 50`: in "Fonti" finisce solo ciò che è stato citato davvero.
`_suggested_wait()` legge il ritardo consigliato dal 429 e distingue la quota al
minuto, dove si aspetta, da quella giornaliera, dove aspettare è inutile.

## 6. Stato condiviso — `frontend-verde/src/app/state.ts`

I signals che chat e mappa scrivono entrambe: `highlighted` (gli alberi
dell'ultima risposta), `selected`, `hovered`, `openArticle`, più `cadastre` e
`messages`. `load()` interroga prima `/api/health` e poi scarica: un errore
all'avvio dice *quale* è il problema invece di limitarsi a fallire. `ask()`
consuma lo stream evento per evento; `api.ts` legge il `ReadableStream`
accumulando in un buffer, perché un chunk di rete può spezzare un JSON a metà.

## 7. Resa — `format.ts`, `chip.ts`, `map.ts`, `chart.ts`

`segment()` non è un parser Markdown: isola `ALB-0042` e `Art. 10` in pezzi
tipizzati, perché diventino targhette cliccabili invece che testo morto.
`chip.ts` è quella targhetta.
`map.ts` tiene Leaflet allineato allo stato con degli `effect`: gli alberi citati
restano accesi, gli altri sbiadiscono, hover e click viaggiano nei due sensi.
`chart.ts` disegna barre orizzontali e usa il colore solo dove porta
informazione: le quattro classi di rischio, che hanno una scala ordinata propria.

## 8. Verifica — `backend/test_*.py` e `backend/eval/`

Cinquantatré test senza chiamate al modello: catasto (21), ciclo dell'agente
(12), RAG (6), citazioni (6), quota (5), endpoint (3), più sette sul frontend
per `segment()`. `test_agent.py` sostituisce solo `generate_content_stream` con
chunk finti costruiti coi tipi veri dell'SDK: turni, dispatch dei tool, un
argomento fuori schema che rientra nel contesto come errore correggibile e il
tetto sui sei giri si verificano offline, senza chiave e senza quota.

`eval/cases.json` è la suite sull'agente vero: dieci casi che dichiarano quali
tool devono essere chiamati, **quali non devono esserlo**, cosa deve comparire
nella risposta e cosa non deve comparire. Il confronto è per parola intera, non
per sottostringa — cercare `6` lo trovava dentro `36` e dentro `ALB-0006`, e un
caso poteva passare per il motivo sbagliato. **Quattro dei dieci verificano che
l'agente rifiuti:** dato assente, domanda fuori dominio, luogo inesistente,
quartiere inesistente. Su quei quattro il controllo che porta il peso è
`expected_citations: "none"` — un rifiuto non può accompagnarsi a delle fonti.

---

## Note di progetto — scelte e limiti dichiarati

1. **Dati inventati.** Alberi generati e regolamento scritto per il progetto,
   non dati R3GIS. Il seed è fisso perché la demo sia riproducibile, e il
   GeoJSON dichiara la propria epoca (`generated_on`): i mesi trascorsi dalle
   ispezioni si contano da lì, non da `date.today()`. Altrimenti il dato resta
   fermo mentre il calendario scorre, l'insieme "non ispezionati da 24 mesi"
   cambia da solo e i conteggi asseriti nei test scadono senza che nessuno
   abbia toccato niente. Con un catasto vero, dove le ispezioni si aggiornano,
   quella funzione torna a essere `date.today()`.
   Limite noto: nessun dato reale ha mai attraversato il sistema.
2. **Due soglie di recupero, e assolute.** `BM25_THRESHOLD = 2.0` e
   `COSINE_THRESHOLD = 0.55`: due perché le scale di punteggio sono diverse,
   assolute perché normalizzando sul migliore il primo risultato vale sempre 1 e
   il sistema citerebbe comunque l'articolo meno peggio. La soglia BM25 è tarata
   sui casi di `test_rag.py`: fuori dominio si arriva a 0.0, la peggiore domanda
   legittima a 2.2. Limite noto: va ritarata se cambiano corpus, tokenizzatore
   o `k1`/`b`. **E sono asimmetriche nella verifica:** quella tarata dai test è
   la BM25, ma con la chiave configurata gira il ramo a embedding, quindi la
   soglia che va in demo è la 0.55 — coperta solo di riflesso, dal caso eval
   fuori dominio.
3. **`comunale` è una stop word *di questo corpus*.** L'intero documento è il
   regolamento di un comune, quindi quella parola non distingue un articolo
   dall'altro. Senza toglierla, "gli orari della biblioteca comunale" pesca
   l'Art. 1 e supera la soglia. Vale però solo per il ramo lessicale:
   `_tokenize` lo usa BM25, il ramo a embedding non passa di lì.
4. **Automatic Function Calling disabilitata di proposito.** Con l'AFC il ciclo
   lo fa l'SDK e non si vede niente; guidandolo a mano si emette un evento per
   ogni chiamata mentre avviene.
5. **Sei turni massimi**, non autonomia illimitata.
6. **PostGIS simulato, ma solo nell'accesso.** La distanza è già quella
   geodetica di `geographiclib` — l'algoritmo di Karney che PROJ porta dentro
   PostGIS — quindi `ST_Distance` darebbe lo stesso numero. Limite noto: manca
   l'indice spaziale, quindi il prefiltro a bounding box resta una scansione.
   Passare a `ST_DWithin` cambia il corpo della funzione, non la firma del tool.
7. **Nessuna autenticazione né autorizzazione.** Limite noto: è il buco più
   grosso. Il principio è però già rispettato — il modello non ha accesso al
   database, ha accesso a cinque funzioni, quindi i permessi andranno dentro
   `_where_clauses()`, mai nel prompt.
8. **Solo italiano.** Limite dichiarato, non svista: un tentativo bilingue
   veloce fa restituire zero alberi a `specie='Linden'`, e per l'agente zero
   significa "non ce ne sono". Il piano completo è in `MULTILINGUA.md`.
9. **Free tier di Gemini**, cinque richieste al minuto. `GEMINI_API_KEYS`
   accetta più chiavi separate da virgola e `keys.py` le fa ruotare: sul limite
   al minuto la chiave va in pausa e ne subentra un'altra — cambiare chiave
   costa zero secondi, aspettare no — sul limite giornaliero esce dal giro e
   viene risondata mezz'ora dopo, perché le quote di Google si azzerano a
   mezzanotte del fuso Pacifico e una chiave esclusa fino al riavvio resta
   fuori anche quando è tornata buona. Si dorme solo per la pausa breve, mai
   per quella lunga: davanti a chi ha fatto la domanda, mezz'ora di attesa e
   un errore sono la stessa cosa. Limite noto: le quote si contano per progetto
   Google, non per chiave, quindi più chiavi dello stesso progetto non servono
   a niente. La suite eval marca `SKIP`, non `FAIL`, i casi morti per quota.
10. **Nessuna scrittura.** Solo GET e POST: è un sistema di consultazione, le
    ispezioni non si registrano.

## Sviluppi futuri

1. PostGIS al posto di SQLite, con indice GiST, e il catasto reale al posto del
   GeoJSON generato.
2. Autenticazione e permessi per layer, applicati dentro i tool e dentro la
   query di recupero — perché il RAG non risolve i permessi.
3. Multilingua italiano/tedesco: etichette localizzate separate dagli
   identificatori, le due versioni ufficiali del regolamento indicizzate
   entrambe con lo stesso `article_id`.
4. Eseguire la suite eval automaticamente ad ogni modifica, e misurare non solo
   se le risposte sono corrette ma anche quanto costano e quanto sono lente,
   come voci separate dal risultato finale.
5. Cache su domanda normalizzata più versione dei dati: i tool sono già
   deterministici.
6. Registrazione delle ispezioni, che è ciò che trasformerebbe l'assistente da
   sola consultazione a strumento di lavoro.
