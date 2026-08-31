# Assistente del catasto del verde

Mini progetto per il colloquio **R3GIS — Frontend AI Product Engineer / AI Champion**
(Bolzano). Chatbot che interroga in linguaggio naturale un catasto alberi, con
risposte ancorate ai dati, citazioni cliccabili e mappa sincronizzata.

---

## 1. Perché questo progetto e non un altro

Dall'annuncio: 75% del ruolo è **progettare esperienze utente basate su AI**, 25%
AI per i workflow interni. TypeScript/JS/HTML/CSS sono richiesti; **Angular è il
primo dei "preferred"**, insieme a REST, data visualization, GIS, PostgreSQL/PostGIS,
Python, Docker. Il dominio è la gestione del verde urbano.

I progetti già presenti in `intervista/` (tool calling, RAG, agente GIS, FastAPI,
Docker) coprono bene il **backend** — cioè la metà che l'annuncio dà per scontata.
Il frontend esistente è un solo `App.tsx`. Quindi qui il backend è volutamente
sottile e il peso sta sul frontend.

Il secondo errore da evitare era riusare l'agente GIS così com'è: geocoding +
meteo non c'entrano con R3GIS. Stessa architettura, **dominio nuovo**: un catasto
alberi con specie, classe di rischio, data di impianto, ultima ispezione, quartiere.

## 2. Cosa fa

Una domanda in italiano → l'agente sceglie i tool → risponde citando le fonti →
la mappa evidenzia esattamente gli alberi di cui ha parlato.

Quattro capacità:

| Capacità | Tool | Esempio |
|---|---|---|
| Filtro attributivo | `search_trees` | "quanti tigli ci sono a Gries?" |
| Query spaziale | `search_trees_near` | "alberi in classe D entro 250 m dalla scuola" |
| Sintesi / grafico | `cadastre_stats` | "distribuzione per classe di rischio" |
| RAG normativo | `consult_regulation` | "ogni quanto va potato un platano?" |

Più `allowed_values`, che il modello chiama quando un quartiere o una specie
potrebbero non esistere — così ammette di non sapere invece di inventare.

## 3. Struttura

```
chatbot/
├── data/
│   ├── trees.geojson          140 alberi finti su 5 quartieri di Bolzano
│   ├── places.json             6 punti di riferimento (scuole, parco, ospedale)
│   └── regolamento_verde.md    11 articoli, il corpus del RAG
├── backend/
│   ├── seed_data.py            genera il catasto (--seed e --epoca finiscono nel dato)
│   ├── cadastre.py             SQLite in memoria + geodetica WGS-84 per lo spaziale
│   ├── rag.py                  embedding Gemini + numpy, fallback BM25 Okapi
│   ├── tools.py                i 5 tool esposti al modello
│   ├── keys.py                 il pool delle chiavi Gemini: pausa vs esaurimento
│   ├── main.py                 FastAPI, /api/chat in streaming SSE
│   ├── tests/                  66 test offline, nessuna rete
│   │   ├── test_cadastre.py    23: catasto, query spaziali, statistiche
│   │   ├── test_agent.py       15: il ciclo dell'agente, con un modello finto
│   │   ├── test_quota.py       13: 429 al minuto vs giornaliero, rotazione chiavi
│   │   ├── test_rag.py          6: chunking, recupero, soglia
│   │   ├── test_citations.py    6: quali fonti finiscono in interfaccia
│   │   └── test_api.py          3: lifespan ed endpoint di lettura
│   └── eval/                   suite di regressione sull'agente (usa il modello)
└── frontend/             Angular 20, standalone + signals, Leaflet
    └── src/app/
        ├── state.ts            signals condivisi fra chat e mappa
        ├── api.ts              client + lettura dello stream SSE
        ├── format.ts           isola i riferimenti (ALB-0042, Art. 10) nel testo
        ├── chip.ts             l'elemento firma: la citazione cliccabile
        ├── chat.ts/.html/.css  conversazione, passi dell'agente, fonti
        ├── map.ts              Leaflet, evidenziazione bidirezionale
        ├── chart.ts            barre orizzontali di sintesi
        ├── types.ts            i contratti condivisi col backend
        └── format.spec.ts      14 test: segment() e citedCodes()
```

## 4. Le decisioni che vale la pena spiegare al colloquio

**Streaming SSE con gli eventi dell'agente, non una risposta sola alla fine.**
`/api/chat` emette `status` → `tool` → `text` → `end`. L'AFC di Gemini è
disabilitata apposta: il ciclo lo guidiamo noi, ed è l'unico modo per mostrare
*quale* tool sta girando *con quali argomenti* mentre gira. Chi guarda vede il
ragionamento, non una rotellina.

**La provenienza è l'interfaccia.** Ogni `ALB-0042` e ogni `Art. 10` nel testo
diventano una targhetta cliccabile. È l'elemento firma del design, ed è preso dal
mestiere: nel rilievo arboreo ogni esemplare porta una targhetta di alluminio
punzonata inchiodata al fusto, ed è quella a rendere il dato verificabile in campo.
Regola pratica: **una frase senza targhetta non ha fonte**.

**Chat e mappa sono la stessa cosa vista due volte.** Quando arriva una risposta,
gli alberi citati restano accesi e il resto del catasto sbiadisce. Hover su una
targhetta → il punto si ingrandisce; click sul punto → si apre la scheda. Lo stato
condiviso vive in `state.ts` e lo scrivono entrambi i lati.

**Il RAG può dire di no.** Le soglie di pertinenza sono assolute, non relative al
miglior risultato: sotto soglia il retriever restituisce zero articoli. Senza
questo, una domanda fuori dominio otterrebbe comunque "l'articolo meno peggio" e
il modello lo citerebbe. È la differenza fra un RAG che sembra funzionare e uno
di cui ci si può fidare.

**Il colore porta dato, non decora.** L'unica scala cromatica dell'interfaccia
sono le quattro classi di propensione al cedimento (A→D). I quattro passi sono
stati verificati con un validatore di palette: la coppia B/C della prima stesura
era indistinguibile in deuteranopia (ΔE 3.3) ed è stata ri-steppata (ΔE 12.4).
L'ocra della classe B resta sotto 3:1 sul fondo, quindi non compare mai da solo:
la lettera è sempre scritta accanto al colore.

**Fallback progettati, non accidentali.** Il retriever passa a BM25 se non c'è
nessuna chiave utilizzabile (i test girano offline e deterministici). Sul 429 lo
stream prima **cambia chiave** e solo se non ce ne sono di libere aspetta,
leggendo il `retryDelay` di Gemini: il free tier concede 5 richieste al minuto e
una demo dal vivo ne consuma 2-3 per domanda. `GEMINI_API_KEYS` ne accetta più
d'una, separate da virgola.

**Lo strato dati è sostituibile.** Le query attributive le fa SQL, quelle spaziali
la distanza geodetica di `geographiclib` dopo un prefiltro a bounding box. In
produzione diventa PostGIS (`ST_DWithin`) senza cambiare la firma dei tool — che
è il punto: i tool sono l'interfaccia stabile, il DB è un dettaglio. E il numero
non cambierebbe: PROJ, sotto PostGIS, porta lo stesso algoritmo di Karney.

## 5. Il 25% interno

`backend/eval/` è la suite di regressione sull'agente: undici casi che dichiarano
quali tool devono essere chiamati, cosa deve comparire nella risposta, cosa non
deve comparire, e che tipo di citazione deve tornare. Quattro casi verificano che
l'agente **rifiuti**: dato assente, domanda fuori dominio, luogo inesistente,
quartiere inesistente.

È lo strumento che serve prima di toccare il prompt, i tool o il modello. È anche
la risposta concreta alla parte "AI Champion" del titolo: portare l'AI nei
processi interni significa prima di tutto poterne misurare le regressioni.

## 6. Demo — cinque domande in difficoltà crescente

1. **Filtro semplice** — "Quanti tigli ci sono nel quartiere Gries?"
   *(mostra: tool calling, conteggio esatto, targhette, evidenziazione in mappa)*
2. **Filtro spaziale + temporale** — "Alberi a rischio moderato o elevato non
   ispezionati da almeno 24 mesi entro 400 m dalla Scuola Primaria Gries"
   *(mostra: composizione di più filtri, distanza reale, ordinamento)*
3. **Domanda normativa** — "Ogni quanto va potato un platano secondo il regolamento?"
   *(mostra: RAG, citazione dell'articolo, lettore del testo di legge)*
4. **Aggregazione + grafico** — "Plottami gli alberi della zona più centrale
   della città per categoria a,b,c,d"
   *(mostra: il quartiere dedotto senza che sia nominato, il grafico disegnato
   dall'interfaccia e non dal modello, la mappa che illumina gli stessi alberi
   che le barre contano)*
5. **Domanda senza risposta** — "Qual è il valore economico stimato degli alberi
   di Oltrisarco?"
   *(mostra: l'agente ammette che il dato non c'è — nessuna citazione, nessuna stima)*

La quinta è la più importante: è quella che dimostra che le prime quattro sono
affidabili.

## 7. Angular

Scritto in Angular 20 (standalone components, signals, `@if`/`@for`) invece di
riusare la shell React esistente. È una scelta deliberata: Angular è il primo dei
"preferred" nell'annuncio, e realizzarlo davvero è un segnale più forte del
dichiarare di saperlo fare.

## 8. Limite dichiarato: l'assistente parla solo italiano

R3GIS sta a Bolzano, provincia bilingue, e l'annuncio chiede ottimo inglese.
Quindi il multilinguismo è un requisito di dominio, non un extra — e questo MVP
**non lo copre**. È una scelta, non una svista.

Il tentativo sbagliato, che ho fatto e poi tolto, è istruttivo: dire al modello
"rispondi nella lingua della domanda" e allargare le regex delle citazioni per
accettare `Article` e `Artikel`. In dieci minuti sembra funzionare, e nasconde
tre rotture silenziose:

- `specie='Linden'` restituisce **0 alberi**, non un errore. Per l'agente zero
  significa "non ce ne sono", quindi risponde *"non ci sono tigli a Gries"*.
  Falso, e detto con sicurezza.
- Il RAG lessicale su un corpus italiano interrogato in inglese restituisce
  **0 articoli**, quindi *"il regolamento non lo prevede"*. Idem.
- Le etichette dell'interfaccia restano italiane in mezzo a una risposta inglese.

Il problema non è la traduzione: è che la lingua era spalmata sul codice invece
di stare in uno strato.

Il piano completo per toglierlo — modello dati, corpus, recupero, fasi di
rilascio — sta in [MULTILINGUA.md](MULTILINGUA.md). Qui il riassunto.

### Come si farebbe sul serio

**Prima cosa: sono due problemi distinti**, e confonderli è l'errore di partenza.

1. **i18n dell'interfaccia** — cataloghi di messaggi (ICU MessageFormat), locale
   preso dal profilo utente o da `Accept-Language`. In Angular è `@angular/localize`
   o Transloco. Non c'entra nulla con l'LLM.
2. **Multilinguismo dei contenuti** — riguarda i dati e il corpus, e si risolve
   a strati.

**Strato dati: separare identificatori ed etichette.** `ALB-0042`,
`Tilia cordata`, `classe D` sono identificatori e non si traducono mai.
`common_name` invece è un'**etichetta localizzata**: oggi sta come colonna
sull'albero ("Tiglio"), e per questo `Linden` non trova niente. Al suo posto va
una tabella `(concept_id, lang, label)` — `tiglio` / `Linde` /
`lime tree` come etichette dello stesso concetto — e il filtro risolve
etichetta → id prima di toccare il DB. Nessuna traduzione a runtime, nessuna
tabella di sinonimi sparsa nel codice.

**Strato corpus: indicizzare le versioni ufficiali, non tradurre al volo.** In
Alto Adige il regolamento *esiste già* in italiano e tedesco, entrambe versioni
ufficiali. Si indicizzano entrambe, ogni chunk marcato con `lingua` e con un
`article_id` condiviso: la citazione resta indipendente dalla lingua e
l'interfaccia mostra la versione giusta. Dove la traduzione ufficiale non
esiste, si traduce **una volta, offline, con revisione umana**, e si marca il
chunk come non ufficiale. Su testo normativo non si traduce mai a runtime: una
frase di legge tradotta al volo da un LLM è una responsabilità legale, non una
funzione.

**Strato recupero: due strategie, entrambe legittime.**

- *Embedding multilingui* (LaBSE, BGE-M3, multilingual-E5, Cohere
  embed-multilingual): lingue diverse finiscono nello stesso spazio vettoriale,
  quindi una domanda in tedesco trova un documento italiano senza alcuna
  traduzione. È la strada pulita.
- *Traduzione della query* (tRAG) o *dei documenti* (CrossRAG): più semplice,
  utile quando serve anche il lessicale.

In pratica si fa ibrido: denso multilingue **più** un indice BM25 **per lingua**,
ognuno col suo analizzatore e le sue stopword — ed è lì che va la lista di
parole vuote italiane che oggi sta in `rag.py`, non in un modulo unico.

Un tranello documentato in letteratura: la generazione peggiora quando i passi
recuperati sono in una lingua diversa dalla domanda. Quindi nel reranking si
preferisce il chunk nella lingua dell'utente, e se si è costretti a usarne uno
in un'altra lingua **lo si dichiara**.

**Strato generazione: il locale è un parametro, non un indovinello.** Arriva
dalla richiesta, non si deduce dal prompt, e il system prompt è parametrizzato
su quello. La lingua di uscita diventa un contratto verificabile.

**Strato valutazione: la suite si moltiplica per lingua.** Non due casi in più:
le stesse domande in ogni lingua supportata, che verificano recupero, lingua
della risposta e integrità delle citazioni.

### Perché per un colloquio va bene così

Un MVP monolingua con il limite dichiarato e il disegno completo pronto da
raccontare vale più di una demo bilingue che si rompe alla seconda domanda. E la
domanda "come lo estenderesti al tedesco?" è, in quel contesto, quasi certa.

## 9. Cosa direi che manca per la produzione

- Autenticazione e permessi per layer: chi vede quali alberi.
- Cache delle risposte e dei risultati dei tool; oggi ogni domanda ricalcola.
- PostGIS al posto di SQLite, e il catasto reale al posto del GeoJSON generato.
- Valutazione continua: la suite eval in CI, non a mano.
- Osservabilità: tracciare tool, latenza e costo per conversazione.
- Il rate limit del free tier non è una strategia: in produzione servono quote
  vere e un degrado esplicito quando finiscono.

## 10. Avvio

Vedi [COMANDI.md](COMANDI.md).
