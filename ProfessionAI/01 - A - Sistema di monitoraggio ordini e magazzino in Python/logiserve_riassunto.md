# LogiServe — sistema di monitoraggio ordini e magazzino — riassunto

**Fonte:** `logiserve.py`
**Caso:** LogiServe S.r.l., piccola realtà di e-commerce B2B che distribuisce componenti elettrici
a officine e rivenditori.
**Cos'è:** un applicativo a riga di comando che simula il gestionale di magazzino.
**Requisiti:** Python 3.8+, sola libreria standard (`csv`, `difflib`, `json`, `os`, `datetime`).
Al primo avvio i file di dati vengono creati in `data/` con dati di esempio, storico incluso.

**Le sette funzionalità della traccia:** registrazione ordini con verifica della disponibilità,
evasione con aggiornamento delle giacenze, carico e rettifica del magazzino, consultazione,
report giornaliero, persistenza su file, tracciabilità delle operazioni. Sotto, gli otto blocchi
in cui lo script le realizza.

---

## 1. Configurazione

Tutti i valori che i dati usano per parlare di sé stessi sono nominati qui e mai scritti a mano nel
codice: percorsi dei file, stati dell'ordine (`new`, `partial`, `fulfilled`), priorità (`high`,
`normal`), nomi delle operazioni loggate, cause di movimento (`order` / `manual`), formato data
unico per scrittura, lettura e validazione.

## 2. Persistence

`load_json()` / `save_json()` / `save_state()`. Al primo avvio i file mancanti vengono seminati
con i dati di esempio (`SEED_CATALOG`, `SEED_ORDERS`, `SEED_LOG`).

## 3. Logging

`init_log()`, `log_operation()`, `read_log()`, `parse_movement()`. Lo storico è un CSV con
timestamp, operazione, risorsa, dettaglio e operatore. Solo `OP_STOCK_UPDATE` viene riletto — dal
report — quindi è l'unico dove un refuso farebbe contare zero in silenzio.

## 4. Warehouse

`find_product()`, `search_products()`, `suggest_code()`, `needs_reorder()`, `change_stock()`,
`print_warehouse()`. Per scegliere un prodotto non serve conoscere i codici: basta digitare parte
del nome o della categoria e selezionare dalla lista.

## 5. Orders

`availability_of()` confronta il richiesto con la merce presente, raggruppando prima le righe per
codice: lo stesso prodotto può comparire su più righe e a coprire la richiesta è la somma, non
ciascuna riga per conto suo. `fulfillment_sequence()` ordina per urgenza e, a parità, per data più
vecchia, con l'id crescente a decidere fra ordini dello stesso giorno. `fulfill_order()` spedisce
il massimo possibile su ogni riga e lascia il resto in attesa: l'ordine diventa `fulfilled` solo se
tutte le righe sono complete, `partial` se qualcosa è uscito, e resta `new` se non c'era niente da
spedire. **Scavalcare la sequenza resta possibile, ma il programma dice chi si sta superando e
chiede conferma.**

## 6. Reporting

`build_daily_report()` ricostruisce la giornata leggendo **lo storico e non gli ordini**: ordini
ricevuti, evasi, in sospeso, i primi cinque prodotti più venduti e la variazione delle giacenze.
`export_report()` scrive il testo su file.

## 7. UI helpers

Le eccezioni `BackToMenu` e `QuitProgram` governano i tre tasti globali, validi al menu e a ogni
singola domanda:

- `?` spiega l'operazione in corso e cosa è richiesto in quel passaggio;
- `h` annulla e torna al menu;
- `q` salva tutto ed esce.

Qui stanno anche `ask_text()`, `ask_yes_no()`, `ask_int()`, `ask_product_code()`, `ask_priority()`,
`ask_date()` e `closest_match()`, che usa `difflib` per tollerare i refusi.

## 8. UI actions e main loop

Una funzione per voce di menu — `action_new_order()`, `action_fulfill()`, `action_warehouse()`,
`action_adjust_stock()`, `action_report()` — e un `main()` con menu testuale, alias dei comandi e
salvataggio all'uscita. L'interruzione da tastiera è gestita: i dati restano salvati all'ultima
operazione completata.

---

## Note di progetto — scelte e limiti dichiarati

1. **Operatore a testo libero**, senza elenco utenti né autenticazione: il nome serve solo a
   firmare le operazioni.
2. **Operatore conservato anche nei dati** (`registered_by`, `fulfilled_by`), non solo nello
   storico. Limite noto: con evasioni parziali ripetute l'ordine tiene solo l'ultimo operatore e
   l'ultima data, quindi il report di una giornata passata può cambiare a posteriori.
3. **Cliente a testo libero**, senza anagrafica. Limite noto: due grafie diverse dello stesso
   cliente risultano due clienti distinti.
4. **Carico per lotti d'acquisto** e non per singole unità: avvicina il comportamento a quello di
   un magazzino reale, dove la merce arriva nel confezionamento del fornitore.
5. **Dati di esempio inventati**, per rendere il programma provabile subito.
6. **Storico coerente con i dati di esempio**: il log seminato riproduce i movimenti dei due ordini
   di esempio, altrimenti il report mostrerebbe un ordine evaso senza merce uscita. Limite noto: i
   tre file si seminano in modo indipendente, quindi per tornare ai dati iniziali va cancellata
   l'intera cartella `data/`.
7. **Tasti globali solo dove il programma pone una domanda**: le due voci di sola lettura stampano
   e tornano al menu, quindi non offrono un punto in cui premerli.
8. **Tolleranza ai refusi** con `difflib` in tre punti — codice prodotto, ID ordine, comando di
   menu — sempre come suggerimento e mai come sostituzione automatica. La soglia sui comandi (0.6)
   è più severa di quella sui codici (0.5): un comando sbagliato si ribatte in un istante, un
   codice no.
9. **Scorte negative impedite anziché gestite**: la giacenza non scende mai sotto zero, perché
   sarebbe un numero che non corrisponde a niente in magazzino; il residuo da consegnare è già
   scritto sulle righe degli ordini, che è il posto in cui serve.
10. **Nomi dei campi in inglese** come il resto del codice, con la tabella di corrispondenza verso
    i nomi italiani della traccia. Due differenze non sono solo di nome: `stock` è la giacenza
    corrente e non quella iniziale, e `lot_size` è un campo in più, richiesto dal punto 4.
11. **Disponibilità misurata sulla giacenza, non sugli impegni**: alla registrazione non viene
    sottratta la merce già promessa agli ordini aperti.

## Sviluppi futuri

1. Inserimento di nuovi prodotti a magazzino, oggi possibile solo modificando il file catalogo.
2. Anagrafica clienti, con codice identificativo proprio.
3. Gestione degli operatori con permessi differenziati per ruolo.
4. Reportistica automatica: il report della giornata precedente generato all'avvio.
5. Annullamento e correzione di un ordine già registrato — da scrivere nello storico con operatore
   e motivo, perché un ordine che sparisce senza traccia varrebbe meno del problema risolto.
