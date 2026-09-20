# Modello per l'identificazione della lingua di testi per un museo — riassunto

**Fonte:** `Modello_identificazione_lingua_museo_Teo .ipynb`
**Caso:** MuseumLangID. Le descrizioni degli oggetti sono in più lingue e la lingua va oggi
riconosciuta a mano.
**Obiettivo:** un modello che identifichi la lingua (it / en / de) e sia facile da integrare nel
sistema esistente del museo.
**Dati:** 294 descrizioni, due colonne, tre lingue da 98 esempi ciascuna.

---

## 0. Ambiente

Fissiamo `nltk`, richiesto dalla consegna, e la versione di scikit-learn. La funzione di pulizia
viene scritta in un modulo a parte (`museum_language_model.py`) e non nel notebook: è quello che
rende il modello salvato caricabile in un processo che il notebook non l'ha mai visto.

## 1. Caricamento e ispezione

Nessun valore mancante, nessun duplicato, target perfettamente bilanciato: l'accuratezza è quindi
leggibile e il riferimento minimo è il ~33% di chi tira a indovinare. Va però notato che
**294 righe sono poche**: con uno split 80/20 il test set conterà una sessantina di esempi.

## 2. Analisi esplorativa dei testi

- **lunghezza** — mediana 6 parole, minimo 2: non sono paragrafi ma didascalie da cartellino.
  È il vincolo che condiziona ogni scelta successiva, perché molte tecniche NLP standard
  presuppongono documenti più lunghi;
- **il tedesco** ha meno parole ma più caratteri dell'inglese: la composizione nominale concentra
  in una parola quello che le altre lingue distribuiscono su tre;
- **diacritici** — il segnale più intuitivo è molto più raro del previsto: i caratteri tedeschi
  compaiono in 36 descrizioni su 98, le vocali accentate italiane in 12 su 98. Affidabili quando
  ci sono, troppo sparsi per fondarci un modello;
- **parole più frequenti** — sono parole funzione, non di contenuto: `con`, `with`, `mit`. Cioè
  esattamente ciò che nella classificazione tematica si butta via come rumore.

## 3. Pulizia e normalizzazione

Minuscolo, via marcatori e punteggiatura, alfabeto da 71 a 34 caratteri distinti — ma **lettere
accentate conservate**. Normalizzare `à` in `a`, come farebbe la pulizia abituale, cancellerebbe
un predittore.

## 4. Tokenizzazione

Tokenizziamo con `nltk` come chiede la consegna e misuriamo due proprietà del vocabolario:

- **sparsità** — 1789 token per 866 parole distinte, di cui 580 compaiono una volta sola: due
  terzi del vocabolario è un hapax, e questo rende fragile qualunque rappresentazione a parole;
- **peso delle stopword** — le liste `nltk` coprono fra il 23,2% e il 29,3% dei token. Rimuoverle
  butterebbe via circa un quarto del corpus, e proprio il quarto più informativo. **Non le
  rimuoviamo.**

## 5. Rappresentazione numerica

Confrontiamo conteggi e TF-IDF, parole e n-grammi di caratteri, per numero di feature e densità
della matrice. Fra parole e caratteri la differenza non è il numero di colonne ma la densità: dal
0,69% al 3,58% di celle non nulle. Su testi corti serve proprio questo — molte evidenze
indipendenti per la stessa decisione. Spingersi a 5 caratteri non conviene: le sequenze coincidono
con parole intere e riportiamo il problema di partenza.

## 6. Split e protocollo di validazione

Split stratificato: 235 in addestramento, 59 in test, dove un singolo errore vale 1,69 punti. Le
decisioni si appoggiano quindi alla cross-validation, e il test set resta la stima finale.
Il numero che chiude la questione della rappresentazione: **il 47,6% delle parole del test set non
compare mai in addestramento**.

## 7. Baseline

Il classificatore banale si ferma al 32,2%, come atteso. Ma la sola frequenza delle singole
lettere raggiunge **l'84,7%**: lo spazio contendibile dal modello non va dal 33% al 100%, va
dall'85% al 100%.

## 8. Addestramento

`GridSearchCV` su rappresentazione, pesatura e smoothing, senza mai guardare il test set. Decide
due cose, entrambe contro l'abitudine:

- **n-grammi di caratteri fino a 4** anziché parole — una parola mai vista è comunque fatta di
  sequenze già viste;
- **IDF scartata** — l'IDF abbassa il peso dei termini diffusi, ma qui i termini diffusi dentro
  una lingua *sono* il segnale.

La normalizzazione della lunghezza resta fuori dalla griglia di proposito: per la metrica di
selezione è un peggioramento, ma senza di essa le probabilità restituite non misurano più niente,
e sono la grandezza su cui si regge la sezione 10.3.

## 9. Valutazione

Sul test set il modello classifica correttamente **tutte e 59 le descrizioni**: le quattro
metriche richieste valgono 1,00 e la matrice di confusione è diagonale. Da leggere con cautela —
59 su 59 non è un'accuratezza del 100%, è l'assenza di errori osservati su un campione piccolo.

Su sei frasi museali esterne al dataset (domande e avvisi al pubblico) risponde 6/6. Non è una
misura, ma falsifica un'ipotesi precisa: che il modello abbia imparato il formato delle didascalie
di questo museo invece della lingua.

## 10. Diagnostica — dove il modello cede

- **10.1 curva di apprendimento** — con 21 esempi è già all'86,8%, da 102 in poi resta sopra il
  98%: **raccogliere altre didascalie non migliorerebbe il modello**. Ne segue anche che
  aggiungere una quarta lingua costerebbe poche decine di esempi;
- **10.2 didascalie brevi** — tronchiamo i testi del test set: con una parola sola 81,4%, con due
  89,8%, con tre 96,6%, **da quattro in su nessun errore**. È la soglia operativa da comunicare al
  personale: sotto le quattro parole la predizione è un suggerimento, non un'etichetta;
- **10.3 lingue non supportate** — escludendo una lingua dall'addestramento, il modello la
  classifica quasi sempre come inglese, e lo fa con margine di confidenza alto (0,893 senza
  l'italiano). Sbaglia con sicurezza: i margini non separano in modo netto le lingue note da
  quelle escluse, quindi un filtro di rifiuto non si riesce a costruire. **È il limite più serio
  del progetto.**

## 11. Integrazione

Il modello viene salvato e **riverificato dopo il ricaricamento da file**, non sulla variabile di
sessione: predice identico su tutte e 294 le descrizioni e accetta testo grezzo, maiuscole e
marcatori HTML inclusi, perché la pulizia viaggia dentro la pipeline.

Salviamo due copie e le proviamo in una directory dove il modulo non esiste:

- `joblib` — formato standard di scikit-learn, tiene la pulizia **per riferimento**: senza il
  modulo accanto non si carica affatto;
- `cloudpickle` — tiene la funzione **per valore**, i byte viaggiano nel file: predice comunque.
  Il museo può ricevere un file solo, al prezzo di una pulizia congelata.

## 12. Conclusioni

Pipeline Naive Bayes su n-grammi di caratteri fino a 4, senza IDF. Il 1,00 sul test set va letto
insieme a tre misure: la baseline all'84,7% (7), la curva che si appiattisce a ~100 esempi (10.1),
e i due casi che il test set non contiene — testi brevissimi (10.2) e lingue non supportate
(10.3). Il dataset è anche favorevole: lingue con parole funzione molto diverse, testi omogenei,
classi bilanciate. Su dati così **la scelta della rappresentazione conta più di quella
dell'algoritmo**.

**Scelte di progetto** (dalle note finali): diacritici conservati, stopword non rimosse, n-grammi
di caratteri anziché di parole, IDF scartata, normalizzazione tenuta fuori dalla griglia, un solo
modello e non tre — la consegna elencava Naive Bayes, SVM e Random Forest come esempi, non come
obbligo.
