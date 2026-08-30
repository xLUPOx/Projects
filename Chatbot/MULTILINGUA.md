# Piano: portare l'assistente al multilingua

Documento di progetto per estendere l'assistente del catasto del verde a italiano,
tedesco e inglese. Non è implementato: l'MVP è monolingua per scelta, e questo è
il disegno con cui si toglierebbe il limite.

Contesto: R3GIS opera a Bolzano, provincia bilingue per statuto, e l'annuncio
richiede ottimo inglese. Il multilinguismo qui è un **requisito di dominio**, non
una funzione accessoria.

---

## 1. Dov'è il problema oggi

Lo stato attuale, verificato sul codice:

| Punto | File | Comportamento in lingua diversa |
|---|---|---|
| Prompt di sistema | [backend/main.py](backend/main.py) | `Parli italiano.` — risponde sempre in italiano |
| Nome comune specie | [backend/cadastre.py](backend/cadastre.py) | `species='Linden'` → **0 alberi**, non un errore |
| Corpus normativo | [data/regolamento_verde.md](data/regolamento_verde.md) | documento solo italiano |
| Stopword e stemming | [backend/rag.py](backend/rag.py) | lista di stopword italiana e stemmer Snowball italiano, uno solo per tutto l'indice |
| Riconoscimento citazioni | [backend/main.py](backend/main.py), [frontend/src/app/format.ts](frontend/src/app/format.ts) | riconosce `Art. N`, non `Article` / `Artikel` |
| Etichette interfaccia | tutto il frontend | stringhe italiane scritte nei template |
| Suite di valutazione | [backend/eval/cases.json](backend/eval/cases.json) | attese in italiano |

**Il rischio non è che non funzioni: è che sembri funzionare.** Nessuno di questi
punti dà errore. Danno **zero risultati**, e per l'agente zero significa "non
esiste". Una domanda in tedesco sui tigli otterrebbe *"non ci sono tigli a
Gries"*; una in inglese sulla potatura, *"il regolamento non lo prevede"*.
Entrambe false, entrambe dette con sicurezza — cioè il difetto esatto che questo
progetto è costruito per prevenire.

---

## 2. Due problemi, non uno

Confonderli è l'errore di partenza.

**A. Internazionalizzazione dell'interfaccia.** Etichette, pulsanti, formati di
data e numero. Si risolve con un catalogo di messaggi. Non c'entra nulla con
l'LLM.

**B. Multilinguismo dei contenuti.** I dati del catasto e il corpus normativo.
Si risolve a strati, ed è il grosso del lavoro.

---

## 3. Strato dati: identificatori contro etichette

La distinzione che regge tutto il resto.

**Identificatori** — non si traducono mai: `ALB-0042`, `Tilia cordata`,
`classe D`, `Art. 10`, i codici dei quartieri.

**Etichette localizzate** — esistono in ogni lingua supportata: "Tiglio" /
"Linde" / "lime tree", "Buono" / "Gut" / "Good", i nomi dei quartieri nella
versione italiana e tedesca (Gries è ufficialmente bilingue).

Oggi `common_name` è una colonna sulla riga dell'albero, ed è per questo che
`Linden` non trova niente. Va estratta:

```
trees(id, species_id, district_id, risk_class, …)   -- solo identificatori

labels(concept_id, kind, lang, label, primary)
   ('tilia_cordata', 'species', 'it', 'Tiglio',    true)
   ('tilia_cordata', 'species', 'de', 'Linde',     true)
   ('tilia_cordata', 'species', 'en', 'Lime tree', true)
   ('tilia_cordata', 'species', 'it', 'Tiglio selvatico', false)   -- sinonimo
```

Il filtro risolve **label → concept_id** prima di toccare il DB. Le query
restano identiche, e `_where_clauses` in `cadastre.py` smette di fare `LIKE` su testo
libero. Nessuna traduzione a runtime, nessun dizionario di sinonimi sparso nel
codice.

Effetto collaterale utile: la stessa tabella serve i sinonimi nella stessa
lingua, che oggi mancano ("farnia" e "quercia comune" sono lo stesso albero).

Il tool `allowed_values` restituisce le etichette nella lingua della richiesta,
così il modello vede il vocabolario giusto e non deve indovinare.

---

## 4. Strato corpus: indicizzare le versioni ufficiali

**Non si traduce il regolamento a runtime.** In Alto Adige esiste già in
italiano e tedesco, entrambe versioni ufficiali con pari valore legale. Una
frase di legge tradotta al volo da un LLM è una responsabilità, non una
funzione.

Ogni chunk porta due campi in più:

```
chunk(article_id, lang, text, official)
   ('art_10', 'it', 'Il platano va potato…',        true)
   ('art_10', 'de', 'Die Platane ist alle…',        true)
   ('art_10', 'en', 'Plane trees must be pruned…',  false)   -- tradotta, revisionata
```

- `article_id` è condiviso: **la citazione è indipendente dalla lingua**. Il
  frontend mostra `Art. 10` e apre il testo nella lingua dell'utente, e le
  targhette continuano a funzionare senza toccare `format.ts`.
- `official = false` va mostrato all'utente: "traduzione di cortesia, fa fede
  la versione italiana". Dove la traduzione ufficiale non c'è, si traduce **una
  volta, offline, con revisione umana**, e si versiona.

---

## 5. Strato recupero

Due strategie, entrambe legittime.

**Embedding multilingui** — LaBSE, BGE-M3, multilingual-E5, Cohere
embed-multilingual. Lingue diverse finiscono nello stesso spazio vettoriale:
una domanda in tedesco trova un documento italiano senza tradurre nulla. È la
strada pulita, e il codice cambia poco: si sostituisce il modello in
`rag._try_embeddings` e si indicizzano i chunk di tutte le lingue.

**Traduzione di query o di documenti** — più semplice, serve quando si vuole
tenere anche il lessicale.

In pratica si fa **ibrido**: denso multilingue più un indice BM25 **per lingua**,
ognuno col suo analizzatore, le sue stopword e il suo stemmer. È lì che va la
lista `STOP_WORDS` italiana che oggi sta in `rag.py` — una per lingua, non una
sola condivisa. Lo stemmer Snowball c'e' gia', ma e' istanziato una volta
sull'italiano: serve uno stemmer per lingua (Snowball ha anche il tedesco) e,
sul tedesco, una decomposizione dei composti — `Baumschutzverordnung` non si
riduce a `Baum` da solo.

**Un tranello documentato in letteratura:** la generazione peggiora quando i
passi recuperati sono in una lingua diversa dalla domanda. Quindi nel reranking
si preferisce il chunk nella lingua dell'utente, e se si è costretti a usarne
uno in un'altra lingua **lo si dichiara nella risposta**.

Le soglie assolute di `rag.py` (`BM25_THRESHOLD`, `COSINE_THRESHOLD`) vanno ritarate
per lingua: sono numeri empirici, non costanti universali.

---

## 6. Strato generazione

**Il locale è un parametro della richiesta, non un indovinello.** Arriva dal
client — profilo utente o `Accept-Language` — e viaggia nel corpo di
`/api/chat`. Non si deduce dal testo della domanda: un utente tedesco che scrive
un termine italiano non ha cambiato lingua.

Il system prompt diventa parametrizzato sul locale, e la lingua di uscita
diventa un contratto verificabile invece di una speranza. `_article_cited` in
`main.py` riconosce le forme di ogni lingua supportata (`Art.`, `Artikel`,
`Article`), e la stessa espressione va tenuta allineata in `format.ts` — un solo
punto di verità, generato o condiviso, non due regex che divergono.

Anche i messaggi che il backend produce da sé vanno localizzati: le etichette dei
tool in `tools.LABELS`, le sintesi di `_summarize_result`, il messaggio di quota
esaurita. Compaiono in chat accanto alla risposta, e in italiano dentro una
conversazione in tedesco stonano.

---

## 7. Strato interfaccia

Le stringhe escono dai template e finiscono in un catalogo di messaggi:
`@angular/localize` (build separata per lingua, più veloce) o **Transloco**
(cambio lingua a runtime, più adatto qui — a Bolzano un utente passa da una
lingua all'altra nella stessa sessione).

Da localizzare oltre alle etichette: le quattro domande di esempio in
`chat.ts`, la legenda della mappa, i formati di data e numero (`DatePipe` e
`DecimalPipe` col locale giusto), l'attributo `lang` dell'HTML.

I nomi dei quartieri sulle tessere OSM sono già bilingui ("Bolzano – Bozen"):
il basemap non richiede lavoro.

---

## 8. Strato valutazione

La suite si **moltiplica per lingua**, non si allunga di due casi. Ogni caso di
`cases.json` diventa una matrice `(domanda, lingua)` e verifica tre cose:

1. il **recupero** trova gli stessi `article_id` in ogni lingua;
2. la **lingua della risposta** corrisponde al locale richiesto — con un
   rilevatore di lingua, non cercando parole spia, che è fragile;
3. le **citazioni** restano integre: stessi codici albero, stessi articoli.

Il terzo è il più importante: è quello che si romperebbe per primo e in
silenzio.

---

## 9. Piano in fasi

Ordinato per rapporto valore/rischio. Ogni fase è rilasciabile da sola.

**Fase 1 — Interfaccia (bassa complessità, valore immediato)**
Transloco, estrazione delle stringhe, selettore di lingua. L'assistente continua
a rispondere in italiano ma l'applicazione è tedesca o inglese. Già sufficiente
per molti utenti dell'ufficio.

**Fase 2 — Locale come parametro**
`/api/chat` accetta `lingua`. Prompt parametrizzato, `_article_cited` e
`format.ts` allineati su un'unica espressione. Messaggi di sistema localizzati.
L'assistente risponde nella lingua richiesta, ma cerca ancora su dati italiani:
**va rilasciata insieme alla Fase 3**, o si ricade nel falso negativo silenzioso.

**Fase 3 — Etichette dei dati**
Tabella `labels`, migrazione di `common_name` e degli stati fitosanitari,
risoluzione etichetta → id in `_where_clauses`, `allowed_values` localizzato. È la
fase che elimina il caso `Linden → 0 alberi`.

**Fase 4 — Corpus bilingue**
Reperimento della versione tedesca ufficiale del regolamento, chunking con
`article_id` condiviso, campo `official`, avviso in interfaccia sulle
traduzioni di cortesia.

**Fase 5 — Recupero multilingue**
Embedding multilingui, indici BM25 per lingua con stemmer Snowball, reranking
che preferisce la lingua dell'utente, soglie ritarate.

**Fase 6 — Valutazione per lingua**
Matrice dei casi, rilevatore di lingua, controllo di integrità delle citazioni.
In CI, non a mano.

---

## 10. Cosa non fare

Tre anti-pattern, il primo dei quali è stato tentato e scartato in questo
progetto — motivo per cui è in cima.

**Non spalmare la lingua sul codice.** Dire al modello "rispondi nella lingua
della domanda" e allargare qualche regex sembra risolvere in dieci minuti. Non
tocca né i dati né l'indice, quindi lascia intatti tutti i falsi negativi
silenziosi e ne aggiunge di nuovi in punti dove nessuno guarda. La lingua sta in
uno strato o non sta da nessuna parte.

**Non tradurre a runtime il testo normativo.** È un problema legale prima che
tecnico.

**Non dedurre la lingua dal testo della domanda.** Il locale è un dato
dell'utente. Una domanda di tre parole non basta a rilevare la lingua, e a
Bolzano il code-switching è la norma, non l'eccezione.

---

## 11. Decisioni da prendere prima di cominciare

1. **Quali lingue sono un impegno?** Italiano e tedesco sono dovuti per statuto.
   L'inglese è una scelta di prodotto e costa quanto le altre due.
2. **Il regolamento tedesco ufficiale esiste ed è reperibile in formato
   lavorabile?** Determina se la Fase 4 è indicizzazione o traduzione con
   revisione — differenza di un ordine di grandezza.
3. **Chi revisiona le traduzioni non ufficiali?** Serve una persona, non un
   processo.
4. **Cambio lingua a runtime o build per lingua?** Determina Transloco contro
   `@angular/localize`.
5. **Quale modello di embedding?** Va misurato sul corpus reale, non scelto da
   una classifica: i risultati pubblicati non si trasferiscono a un dominio
   tecnico ristretto.

---

## Riferimenti

- [Cross-Lingual & Multimodal RAG](https://apxml.com/courses/large-scale-distributed-rag/chapter-6-advanced-rag-architectures-techniques/cross-lingual-multimodal-rag-scale)
- [Top Multilingual Embedding Models for RAG](https://aimultiple.com/multilingual-embedding-models)
- [Linguistic Nepotism: Trading-off Quality for Language Preference in Multilingual RAG](https://arxiv.org/pdf/2509.13930)
- [XRAG: Cross-lingual Retrieval-Augmented Generation](https://arxiv.org/pdf/2505.10089)
- [Investigating Language Preference of Multilingual RAG Systems](https://arxiv.org/pdf/2502.11175)
