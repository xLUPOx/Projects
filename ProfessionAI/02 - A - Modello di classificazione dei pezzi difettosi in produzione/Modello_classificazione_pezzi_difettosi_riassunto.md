# Modello di classificazione dei pezzi difettosi — riassunto

**Fonte:** `Modello_classificazione_pezzi_difettosi_Teo.ipynb`
**Caso:** AutomaParts S.p.A., fornitore tier-1 automotive. Distinguere in linea i pezzi conformi
dai difettosi a partire da misure dimensionali, parametri di processo, linea e operatore.
**Dati:** 3.000 pezzi, 16 variabili, target binario `defect_label` sbilanciato (~22% difetti).

---

## 1. Caricamento e ispezione del dataset

Carichiamo il CSV dall'URL della consegna con `parse_dates` sul timestamp, poi `info()` e
`describe()`: identificativi (`part_id`, `line_id`, `station_id`, `operator_id`,
`material_batch`), una marca temporale, 9 misure numeriche e l'etichetta.

## 2. Analisi esplorativa

- **valori mancanti** — nessuno in tutto il dataset;
- **distribuzione dei difetti** — countplot del target, ~22% difettosi: classe minoritaria da
  gestire con stratificazione e pesi di classe;
- **difetti per feature** — istogrammi con KDE sulle 9 misure numeriche;
- **correlazione feature/target (matrice)** — heatmap: ogni correlazione lineare con il target
  resta sotto 0,10 in valore assoluto;
- **scostamenti dei valori delle feature (boxplot)** — le distribuzioni condizionate alla classe
  si sovrappongono quasi del tutto;
- **confronto con dati aggregati (linea/operatore)** — tasso di difettosità per linea contro la
  media generale;
- **correlazioni linea/operatore vs target** — pivot linea × operatore: la variabilità fra linee
  è più che doppia rispetto a quella fra operatori, ma ogni cella contiene in media ~30 pezzi;
- **relazioni non lineari** — `mutual_info_classif`, per non fermarci al legame lineare.

**Esito.** Il segnale predittivo è debole sia in forma lineare sia non lineare. È l'osservazione
che governa tutto il resto del notebook.

## 3. Pulizia dei dati e gestione dei buchi

- **identifichiamo gli outlier e li teniamo** — la regola IQR ne trova un numero nullo o
  trascurabile; in controllo qualità un valore ai limiti di tolleranza è l'osservazione più
  informativa, non rumore, quindi decidiamo comunque di non rimuoverli.
- Nessun valore mancante nel dataset attuale, ma definiamo lo stesso una strategia di imputazione
  — mediana per le numeriche, moda per le categoriche — da applicare se in produzione dovessero
  comparire letture mancanti.

## 4. Feature engineering

- **creiamo le serie utili** — dal timestamp estraiamo ora, giorno della settimana e mese; dal
  codice lotto la sola settimana di produzione (`material_batch` ha ~2.997 valori distinti su
  3.000: usarlo come categoria porterebbe a overfitting quasi totale). Scartiamo `part_id`;
- **separiamo le variabili numeriche dalle categoriche e cerchiamo correlazioni fra le misure
  numeriche** — `line_id`, `station_id` e `operator_id` sono nominali, quindi One-Hot Encoding e
  non `LabelEncoder`, che imporrebbe un ordine inesistente. La correlazione massima fra due
  predittori numerici non supera 0,05: la multicollinearità non spiega il segnale debole.

## 5. Suddivisione train/test e preprocessing

- **prepariamo le matrici train/test (stratificate)** — split 80/20 con `stratify=y`, perché con
  una minoranza al 22% un singolo split casuale potrebbe dare un test set non rappresentativo;
- **definiamo il preprocessor** — `ColumnTransformer` dentro una `Pipeline`: imputazione con
  mediana e moda, `StandardScaler` sulle numeriche, One-Hot sulle categoriche. Mediana, moda e
  parametri di scaling si apprendono solo sul training set, così non c'è data leakage.

## 6. Ottimizzazione della Regressione Logistica

Selezione in cross-validation con `scoring="f1"`: l'accuratezza sarebbe fuorviante, perché un
modello che predice sempre "conforme" otterrebbe già ~78%.

- **L1** — azzera i coefficienti delle feature poco utili: 37 su 53. Da leggere con cautela, dato
  il segnale debole già osservato;
- **L2** — riduce tutti i coefficienti senza azzerarne nessuno: informazione distribuita, tutte le
  53 feature restano nel modello con pesi contenuti;
- **Elastic Net (L1 + L2)** — invece di scegliere a priori, cerchiamo insieme `l1_ratio` e `C`.
  La ricerca sceglie `l1_ratio=0` con `C=0.01`, cioè l'estremo L2 puro raggiunto *attraverso* la
  ricerca Elastic Net, con differenze di F1 minime fra i vari `l1_ratio`. Il `C` basso conferma
  una regolarizzazione forte.

## 7. Confronto Logistic Regression vs Decision Tree vs Random Forest

- **F1, ROC-AUC, recall, precision** in cross-validation a 5 fold sul training set.

**Esito.** Tutti e tre restano fra ~0,52 e ~0,56 di ROC-AUC, appena sopra il classificatore
casuale: è la conferma quantitativa del segnale debole. Random Forest ha la precision più alta e
il recall più basso, Logistic Regression il profilo opposto.

## 8. Diagnostica dell'overfitting

- **curve train vs cross-validation (cv=5)** — learning curve per i tre modelli.

**Esito.** Le curve restano basse e piatte anche aumentando i dati: è high bias strutturale, non
varianza. Più righe non aiutano; servono feature più informative.

## 9. Valutazione sul set di test

- **matrice vero/falso vs difetto/conforme** — matrici di confusione affiancate per i tre modelli.

**Esito.** ROC-AUC modesto e simile per tutti (~0,55–0,61). Nessun modello vince in assoluto: la
scelta dipende dal costo relativo di un falso negativo rispetto a un falso positivo.

## 10. Threshold della probabilità di classificazione

- **valutazione con beta [il recall conta di più]** — `predict()` usa una soglia fissa a 0,5, che
  va bene solo se i due errori pesano uguale. Con `beta=2` la soglia ottimale scende a 0,30, e da
  `beta=1.5` in poi satura: i falsi negativi sul test set sono già a zero. Con questo potere
  predittivo dare priorità forte al recall equivale quasi a controllare tutto a mano;
- **soluzione a fasce di decisione** — tre zone al posto della risposta binaria, con i tagli presi
  dalle stesse soglie F-beta ricavate dai dati: `low_cut` dalla soglia F-beta 2-ottimale,
  `high_cut` da quella F-beta 0,5-ottimale. Il modello non basta per una decisione binaria
  affidabile, ma resta utile per allocare priorità di ispezione.

## 11. Interpretabilità e feature informative

- **cerchiamo le feature più informative per i modelli diversi** — importances di Random Forest e
  coefficienti della Logistic Regression, ricondotti alle colonne originali.

**Esito.** Le più informative sono `cycle_time_s`, `vibration_level`, `flatness_mm` e
`temp_process_C`: parametri di processo più che misure dimensionali statiche. Le due top-5 non
coincidono, ma limitandosi alle variabili numeriche `cycle_time_s` è la prima per entrambi.

## 12. Verifica della robustezza

Due controlli indipendenti, dalle direzioni opposte.

- **riaddestramento usando solo le feature importanti** — le 10 migliori secondo Random Forest: le
  prestazioni restano nello stesso intervallo, quindi il rumore delle feature poco informative non
  è la causa;
- **riaddestramento con un MLP** — rete neurale con oversampling della classe minoritaria, perché
  `MLPClassifier` non supporta `class_weight`: non supera il ROC-AUC dei tre modelli originari.

**Esito.** Né meno feature né più capacità del modello spostano il risultato: il limite sta
nell'informatività intrinseca delle variabili disponibili.

## 13. Conclusioni

Tutti i modelli provati restano fra ~0,53 e ~0,61 di ROC-AUC, e il risultato è confermato da più
angolazioni indipendenti: correlazioni deboli (2), nessuna multicollinearità (4), `C` basso scelto
dalla cross-validation (6), learning curve piatte (8), due verifiche di robustezza (12).

**Modello consigliato.** Logistic Regression (L2, `C` basso) se la priorità è minimizzare i falsi
negativi; Random Forest se si vuole sfruttare il ranking del rischio dentro il sistema a tre zone
della sezione 10.

**Limiti.** Il potere predittivo non giustifica un'automazione spinta dello scarto; le variabili
dicono *cosa* è stato misurato, non *quanto* ogni misura si discosti dalla tolleranza
ingegneristica specifica; `material_batch` e `operator_id` avrebbero bisogno di più osservazioni
per lotto.

**Raccomandazioni.** Usare il modello come triage a tre zone con soglie calibrate sui costi reali
di FN e FP; dare priorità di manutenzione alle linee sistematicamente sopra la media; spostare
l'intervento a monte con un allarme diretto su `cycle_time_s` e `vibration_level`, misurabili in
tempo reale; ricalibrare a ogni cambio di fornitore, perché un segnale già debole è più
vulnerabile al data drift.
