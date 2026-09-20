# ProfessionAI — progetti del percorso

Sei progetti consegnati durante il master ProfessionAI, dal Python di base al deploy di un
servizio in produzione. Ogni cartella contiene **il progetto** e **il suo riassunto**: il riassunto
è il posto da cui partire, perché spiega le scelte e i limiti che il codice da solo non dichiara.

| # | progetto | tecnologie | cosa risolve |
| --- | --- | --- | --- |
| 01-A | [Sistema di monitoraggio ordini e magazzino](<01 - A - Sistema di monitoraggio ordini e magazzino in Python>) | Python, libreria standard | gestionale a riga di comando con persistenza su file |
| 01-D | [Algoritmo di correzione per un motore di ricerca](<01 - D - Un Algoritmo di Correzione per un Motore di Ricerca>) | Python, distanza di edit | corregge i refusi di una query e propone alternative |
| 02-A | [Classificazione dei pezzi difettosi](<02 - A - Modello di classificazione dei pezzi difettosi in produzione>) | scikit-learn, pandas | riconosce i pezzi difettosi da misure di produzione |
| 02-D | [Identificazione della lingua di testi museali](<02 - D - Un modello per l'identificazione della lingua di testi per un museo>) | scikit-learn, TF-IDF | distingue italiano, inglese e tedesco su didascalie brevi |
| 03-D | [API di riconoscimento della lingua](<03 - D - API riconoscimento lingua museo>) | FastAPI, Pydantic, Vercel | espone il modello 02-D come servizio HTTP in produzione |
| 04-D | [Analisi delle vendite di un e-commerce](<04 - D - Analisi delle vendite di un sito di e-commerce>) | SQL, SQLite | risponde con query a quattro domande di business |

---

## Cosa c'è in ogni cartella

**Il file del progetto** — un notebook `.ipynb`, uno script `.py` o un file `.sql` — e un
**`*_riassunto.md`** che lo accompagna.

I due si leggono insieme e dicono cose diverse:

- **Il file del progetto** contiene il lavoro eseguito, con gli output al loro posto. Nei notebook
  ogni sezione numerata ha il proprio commento di lettura; negli script e nei file SQL le stesse
  spiegazioni stanno nei commenti, e in fondo c'è sempre un blocco **NOTE DI PROGETTO** con le
  scelte fatte, il loro limite noto e gli sviluppi futuri.
- **Il riassunto** è la versione leggibile in cinque minuti: caso d'uso, requisiti, una sezione per
  blocco di codice, e le note di progetto in forma compatta. Se cerchi *perché* una cosa è fatta
  così, sta qui o nelle NOTE DI PROGETTO — non nel codice.

---

## Cosa ho imparato, progetto per progetto

**01-A — Sistema di monitoraggio ordini e magazzino.** Scrivere un applicativo che dura oltre la
sessione: persistenza su file, formati di dato scelti una volta e riletti ovunque, e la disciplina
di far dichiarare a ogni costante *chi la rilegge e cosa si rompe se cambia*. Solo libreria
standard, per capire cosa fanno davvero le dipendenze che altrove si danno per scontate.

**01-D — Algoritmo di correzione.** La distanza di edit e il costo che comporta: confrontare una
query con un intero vocabolario è un'operazione quadratica, e il lavoro vero è restringere i
candidati prima di misurarli. Qui si impara che l'ottimizzazione nasce da come si riduce il
problema, non da come si scrive il ciclo.

**02-A — Classificazione dei pezzi difettosi.** Il ciclo completo di un modello supervisionato:
esplorazione, baseline, confronto fra algoritmi, validazione. La lezione che resta è che **una
metrica alta non significa niente senza una baseline**: finché non sai quanto fa un modello banale,
non sai se il tuo ha imparato qualcosa.

**02-D — Identificazione della lingua.** Un caso in cui la prassi va contraddetta: nella
classificazione tematica le stopword si eliminano, qui **sono il segnale** — e lo stesso vale per
gli accenti, che una normalizzazione di routine cancellerebbe. Si impara anche a leggere una
learning curve: qui è piatta molto prima dell'ultimo campione, cioè i dati smettono di essere
informativi e aggiungerne non serve.

**03-D — API in produzione.** La distanza fra "funziona sul mio PC" e "funziona pubblicato". Tre
vincoli del serverless riscrivono altrettante scelte: filesystem non scrivibile, quindi il log va
su standard output; avvio dalla radice del progetto, quindi i percorsi nascono da `__file__`;
istanze spente a piacere, quindi il modello si carica nel `lifespan`. In più, codici di errore che
distinguono i casi — 400 richiesta mal composta, 409 non lavorabile, 422 non valida — e la
registrazione delle richieste **respinte dalla validazione**, che altrimenti non lascerebbero
traccia proprio dove serve.

**04-D — Analisi delle vendite.** SQL come strumento di analisi e non solo di interrogazione, e
soprattutto **leggere i dati per quello che sono**: qui ogni prodotto ha venduto esattamente due
unità, quindi la classifica per fatturato coincide con il listino prezzi e non dice nulla sulle
preferenze dei clienti. Riconoscere un risultato degenere e dichiararlo vale più che presentarlo
come una scoperta.

---

## Note pratiche

**I notebook** si aprono su GitHub, che li mostra con gli output già eseguiti: per leggerli non
serve installare nulla.

**Il progetto 03-D** è un servizio FastAPI pubblicato su Vercel. Per provarlo in locale:
`pip install -r requirements.txt` e `python app.py`, poi `/docs` per la documentazione
interattiva. La pagina servita su `/` elenca gli endpoint e mostra come chiamarli.

**Il progetto 04-D** è scritto per SQLite, motore che la traccia non imponeva: è quello su cui le
query sono state eseguite davvero, e i risultati riportati sotto ognuna vengono da lì. Le
istruzioni per rieseguirlo stanno in testa al file.

**Lingua.** I documenti e i commenti sono in italiano; identificatori, docstring e titoli dei
grafici sono in inglese.
