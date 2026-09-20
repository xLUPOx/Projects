# XYZ E-commerce — analisi delle vendite in SQL — riassunto

**Fonte:** `analisi_vendite_ecommerce.sql`
**Caso:** il sito e-commerce che ha lo storico di prodotti, clienti e ordini in database e vuole
sapere chi spende, cosa rende e quando si vende.
**Cos'è:** un file di sole query di lettura, diviso in cinque sezioni numerate. Ogni sezione porta
la propria query e, subito sotto, il risultato che quella query produce riportato in un blocco
commentato.
**Requisiti:** SQLite 3. Va eseguito dopo `ecommerce.sql`, lo script di creazione indicato dalla
traccia, che crea le tre tabelle e inserisce le 20 righe di esempio. La traccia chiede un
«database SQL» senza nominare un motore: SQLite è quello su cui il file gira davvero, lo script di
creazione vi si carica senza modifiche e i risultati riportati nei blocchi vengono da lì.

**Le cinque fasi della traccia:** preparare il dataset integrato, calcolare la spesa per cliente e
ordinarla, calcolare il fatturato per prodotto e ordinarlo, aggregare le vendite per giorno della
settimana con la media giornaliera, calcolare media **e** distribuzione dei prodotti per ordine.
Sotto, le cinque sezioni in cui il file le realizza.

**Perché i risultati stanno dentro il file.** Un `.sql` non ha output propri: eseguirlo stampa
qualcosa a schermo e non lascia traccia nel documento. Riportare ogni result set in un blocco
commentato è ciò che permette di citare una cifra nei commenti senza scriverla a mano — ogni numero
del testo si ritrova nella tabella sopra di esso.

---

## 1. Preparazione dei dati

Il `JOIN` fra le tre tabelle è **INNER su entrambi i lati**: una riga di `ordini` le cui chiavi
esterne non risolvessero è una riga rotta, e lasciarla passare gonfierebbe ogni totale calcolato
dopo. Il risultato conta 20 righe, quante ne ha `ordini`, quindi nessuna chiave è orfana.

La sezione registra le **due assenze dello schema** che condizionano tutto il resto: `ordini` non
ha una colonna quantità — ogni riga vale un pezzo, e il prezzo del prodotto è il valore della riga
— e non ha un identificativo d'ordine, che è il problema ereditato dalla sezione 5.

## 2. Analisi dei clienti

`SUM(p.prezzo)` raggruppato per cliente, ordinato in modo decrescente. La somma della colonna dà il
fatturato del periodo, **7779,80 euro**; il top spender vale 3899,95 euro, il **50,1% del totale**.

Accanto alla spesa è selezionata `items_bought`, che non è decorativa: mostra che **la classifica
non segue il numero di articoli**. Tre clienti hanno comprato 4 pezzi a testa e spendono 2199,96,
499,96 e 299,96 euro. È il prezzo medio del carrello a separarli, non la frequenza d'acquisto.

## 3. Analisi dei prodotti

Fatturato per prodotto, con `units_sold` affiancata al totale. Il best-seller è il Laptop con
2199,98 euro, il 28,3% del fatturato.

La colonna delle unità è ciò che rende leggibile il risultato, e dice una cosa scomoda: **tutti e
dieci i prodotti hanno venduto esattamente 2 unità.** Con le quantità costanti il fatturato è il
prezzo moltiplicato per due, e la classifica per fatturato **coincide riga per riga con il listino
prezzi**. Su questi dati "best-seller" e "prodotto più caro" sono la stessa domanda, e la risposta
non dice nulla sulle preferenze dei clienti.

## 4. Analisi temporale

Aggregazione per giorno della settimana, con il fatturato diviso per `COUNT(DISTINCT data)` e non
per il numero di righe: i giorni della settimana non compaiono lo stesso numero di volte nel
periodo, quindi la somma grezza ordinerebbe il calendario invece delle vendite.

Il nome del giorno nasce in due passaggi: `strftime('%w', o.data)` restituisce una cifra, 0 per la
domenica, e una CTE `weekdays` di sette righe la traduce in nome. Tenere i nomi in una tabella
invece che in un `CASE` li rende visibili e modificabili in un punto solo.

Tre dettagli della query non sono cosmetici:

| accorgimento | cosa si romperebbe senza |
| --- | --- |
| la CTE `weekdays` | `strftime` da solo darebbe una cifra, e la colonna sarebbe illeggibile |
| `ROUND(..., 2)` | la divisione non è esatta, e la media del giovedì trascinerebbe una lunga coda di decimali |
| `ORDER BY ..., total_revenue DESC` | sabato e martedì hanno entrambi media 399,99, e senza spareggio il loro ordine reciproco è arbitrario |

Il giorno con la media più alta è il **giovedì con 663,32 euro**. La colonna `days_observed`
ridimensiona subito il risultato: ogni giorno compare 2 o 3 volte e ogni data porta un solo
acquisto, quindi il giovedì vince perché il 2025-01-02 è stato venduto il Laptop. **Il vantaggio
sulla domenica è di 23,33 euro.**

## 5. Analisi degli ordini

La traccia chiede media **e** distribuzione, e sono due query separate: una media di 1,0 potrebbe
in teoria venire anche da un misto di ordini di dimensioni diverse, e solo la distribuzione lo
esclude.

`ordini` non ha un identificativo d'ordine, quindi l'ordine è ricostruito dalla coppia
**`(id_cliente, data)`**: un ordine è ciò che un cliente ha comprato in una giornata. Gli ordini
ricostruiti sono 20 e la media è **1,0 prodotti per ordine**, con minimo e massimo coincidenti e
la distribuzione su una sola classe.

Il risultato è degenere, e la causa sta nei dati e non nella query: **nessun cliente ha comprato
due volte nello stesso giorno**, quindi ogni riga della tabella è già un ordine a sé.

---

## Note di progetto — scelte e limiti dichiarati

1. **L'ordine è ricostruito dalla coppia `(id_cliente, data)`**, perché la tabella non ha un
   identificativo d'ordine. L'alternativa scartata — raggruppare per solo cliente — misurerebbe il
   totale storico e duplicherebbe la sezione 2, restituendo una media di 4 al posto di un numero
   vero. Limite noto: due acquisti dello stesso cliente nello stesso giorno, fatti in sessioni
   distinte, risultano come un ordine solo.
2. **Le unità vendute sono selezionate accanto al fatturato**, una colonna in più rispetto al
   minimo richiesto dalla traccia. Senza di essa la classifica della sezione 3 sembrerebbe una
   graduatoria di popolarità. Limite noto: su un catalogo con quantità variabili le due colonne
   possono ordinare in modo discorde, e va deciso quale risponde alla domanda posta.
3. **La media giornaliera divide per le date osservate, non per le righe.** Dividere per il numero
   di righe darebbe il prezzo medio di un acquisto, non il fatturato di una giornata. Limite noto:
   le giornate senza ordini non esistono nella tabella e restano fuori dalla media — su dati reali,
   dove i giorni a zero vendite sono frequenti, il denominatore corretto è un calendario completo.
4. **Lo script è scritto per SQLite**, motore che la traccia non impone e su cui lo script di
   creazione si carica senza modifiche. L'alternativa, `DAYNAME` di MySQL, darebbe il nome del
   giorno in una sola espressione ma legherebbe il file a quel motore. Limite noto: anche
   `strftime` è specifico di SQLite, quindi portare altrove la sezione 4 significa sostituirlo.
5. **Gli importi sono arrotondati a due decimali con `ROUND`**, perché SQLite somma i prezzi in
   virgola mobile. Limite noto: l'arrotondamento avviene alla lettura e non nei dati, quindi su
   volumi molto maggiori gli importi andrebbero gestiti con un tipo esatto.

## Cosa questi dati non possono dire

Vale come avvertenza a chi legge i risultati, non come difetto delle query. Il campione è di 20
righe su 20 date consecutive, ed è **costruito in modo uniforme**: 2 unità per ogni prodotto, un
solo acquisto per data, nessun ordine multiriga. Da qui vengono i tre limiti registrati nelle
sezioni 3, 4 e 5 — fatturato che ricalca il listino, giorno della settimana deciso da un singolo
prodotto costoso, media degli ordini bloccata a 1,0.

Le query sono quelle giuste e su dati di produzione darebbero risposte utilizzabili: è il campione
a non poterle alimentare. Le tre cose che lo cambierebbero sono una colonna quantità e un
`id_ordine` nello schema, e uno storico di almeno dodici mesi.
