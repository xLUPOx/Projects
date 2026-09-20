# Algoritmo di correzione per un motore di ricerca — riassunto

**Fonte:** `Algoritmo di Correzione per un Motore di Ricerca.ipynb`
**Caso:** Searchify, motore di ricerca interno per aziende medie. Gli utenti sbagliano a digitare
le parole chiave e la ricerca non restituisce nulla ("raporto vendite 2023").
**Obiettivo:** correggere automaticamente la query prima di interrogare il database.
Il notebook è diviso in due: la **Parte A** copre i requisiti della consegna, la **Parte B** li
estende.

---

# Parte A — versione minima

## A1. Dizionario aziendale

Definiamo `ENTERPRISE_DICTIONARY`, esattamente 50 termini unici a parola singola del contesto
aziendale (fatture, magazzino, contabilità, iso-9001…), con una cella di test che ne verifica il
conteggio.

## A2. Acquisizione dell'input

`get_user_query()` chiede la query all'utente e la restituisce grezza, senza toccarla.

## A3. Pulizia e tokenizzazione

`clean_and_tokenize()` normalizza prima di analizzare:

- controllo query vuota;
- normalizzazione Unicode NFC, così le lettere accentate scritte in due modi diversi coincidono;
- rimozione degli spazi ai bordi e minuscolo, per un confronto insensibile alle maiuscole;
- estrazione dei token con una regex che tiene insieme i decimali (`3,14`) e le stringhe con
  trattino (`iso-9001`, `machine-learning`).

Le costanti globali stanno qui: `TOLLERANCE = 2`, `WORD_PERCENTAGE`, `MINIMUM_LENGTH` derivata
dalla parola più corta del dizionario.

## A4. Classificazione dei token

`classify_tokens()` divide i token in quattro stati, così la distanza di edit si calcola solo dove
serve: `numeric` (numeri e decimali), `correct` (già a dizionario), `short` (troppo corti per
essere corretti in modo affidabile), `to_verify` (i soli candidati alla correzione).

## A5. Distanza di Levenshtein, implementata da zero

`calculate_levenshtein_distance()` in programmazione dinamica: matrice
(len_s1 + 1) × (len_s2 + 1), conteggio del numero minimo di inserimenti, cancellazioni e
sostituzioni per trasformare la parola della query in quella del dizionario.

## A6. Ricerca dei candidati e tie-break

- `find_levenshtein_candidates()` filtra prima il dizionario per lunghezza, entro `TOLLERANCE`,
  per non calcolare la distanza su parole che non possono vincere;
- a parità di distanza minima decidiamo con `_get_common_prefix_length()`: fra due candidati
  ugualmente lontani vince quello che condivide con la query il prefisso più lungo, cioè la
  correzione che l'utente percepisce come più naturale.

## A7. Funzione orchestratrice

`suggest_correction()` mette in fila le fasi: pulizia, classificazione, distanza di Levenshtein con
tolleranza dinamica, ricostruzione della stringa finale. Se la somiglianza non è sufficiente il
termine originale resta com'è: preferiamo non correggere piuttosto che correggere male.

## A8. Suite di test

Dieci casi rappresentativi: refusi comuni, parole già corrette, numeri puri, mix italiano-inglese,
codici tecnici e query vuota.

---

# Parte B — versione potenziata

Ogni punto è un delta rispetto alla Parte A.

## B1. Dizionario strutturato a categorie

`ENTERPRISE_DICTIONARY_IT` non è più una lista ma un dizionario di liste (Vendite,
Amministrazione, Logistica…), e contiene anche termini composti ("busta paga", "bilancio
annuale"). Non correggiamo soltanto la parola: la associamo a un contesto aziendale.

## B2. `DictionaryAnalyzer`

Una classe che si occupa del dizionario: statistiche automatiche (parola più corta e più lunga,
numero di categorie, parole per categoria) e costruzione di una mappa *flat* che unisce parole
singole e termini composti. Da qui ricalcoliamo `MINIMUM_LENGTH` e introduciamo
`COMPOUND_MERGE_THRESHOLD`, più conservativa, per le unioni.

## B3. Damerau-Levenshtein

`calculate_damerau_levenshtein()` conta lo scambio di due lettere adiacenti come un solo errore.
È il refuso più comune alla tastiera: `evndite` dista 1 da `vendite`, non 2.

## B4. Termini composti (rolling window)

La Parte A guarda un token per volta. `rolling_window_merge()` guarda le coppie adiacenti e le
unisce solo se l'unione è un miglioramento reale rispetto a trattarle separate — così `bus pga`
diventa `busta paga` senza che `informazioni generali` venga assorbito in un composto sbagliato.
Gestisce refusi su entrambe le parti, l'assenza di spazio (`bustapaga`) e l'ordine invertito.

## B5. Tie-break avanzato e scoring

Il prefisso comune della Parte A viene sostituito da un sistema più robusto:

- `_get_shared_characters_count()` usa `Counter` per contare i caratteri condivisi tenendo conto
  della frequenza di ciascuna lettera;
- `_determine_best_correction()` fa da arbitro: a parità di distanza vince il candidato con più
  caratteri in comune, riducendo i falsi positivi;
- `score_candidates()` unifica la scansione del dizionario, prima duplicata, applicando i filtri
  di lunghezza e ordinando per distanza crescente.

## B6. Decomposizione alfanumerica

`decompose_and_match()` separa la parte alfabetica da quella numerica e usa **i numeri come
ancora**: filtra il dizionario sui termini che contengono quella sequenza numerica e poi confronta
la parte alfabetica. Recupera `iso9001`, `9001iso`, `isooo-9001` — casi che la Parte A non tratta.

## B7. Pipeline orchestrata

`suggest_correction_advanced()` integra tutti i moduli e restituisce un oggetto strutturato, non
una stringa: query corretta **più topic**, cioè la categoria aziendale, pronta per filtrare i dati
a valle. Attorno c'è un `main()` con input continuo, comando `help` che stampa istruzioni e
panoramica del dizionario, e uscita con `q`.

---

## Conclusioni

Il salto fra le due parti non è nell'algoritmo di distanza ma in cosa consideriamo un'unità da
correggere: la Parte A ragiona su token isolati e parole singole, la Parte B su coppie adiacenti,
composti e codici alfanumerici, e restituisce anche il contesto. La correzione resta sempre un
suggerimento fondato su una soglia: quando la somiglianza non basta, il termine originale
sopravvive.
