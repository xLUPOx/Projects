# Sincronizzazione file con multiprocessing e multithreading — riassunto

**Fonte:** `Sincronizzazione_file_Teo.ipynb`
**Caso:** SyncEase, software house di backup e replica. I clienti tengono allineate due cartelle
(un server locale e una destinazione di backup) con script improvvisati: file aggiornati che non
arrivano, duplicazioni, copie che durano ore.
**Obiettivo:** un prototipo in Python che, ricevuti `source_folder` e `destination_folder`, renda
la destinazione una copia coerente della sorgente — copia dei file nuovi, aggiornamento dei
modificati, rimozione degli obsoleti — e che misuri quanto rendono thread e processi.
**Requisiti:** Python 3.12 su Linux (Google Colab), libreria standard più `pandas` per le tabelle.
I processi partono con `fork`, quindi il notebook **non gira su Windows** (vedi note di progetto).

**L'idea che regge tutto il resto:** il motore lavora in due fasi separate. Prima il **confronto**
costruisce la lista delle azioni senza toccare un file, poi l'**esecuzione** la svolge. Ogni fase
usa lo strumento di parallelismo adatto al suo tipo di lavoro, e la lista intermedia si può
stampare, verificare e — con `dry_run` — non eseguire affatto.

---

## 0. Ambiente

Si stampano versione di Python, stato del GIL e CPU disponibili, perché i tempi della sezione 6
vanno letti in rapporto a questi dati: **Python 3.12, GIL attivo, 2 CPU**. Il runtime usa 2
processi e 8 thread. Il log va su file ed è **scritto solo dal processo principale**: i worker
restituiscono cosa hanno fatto, e le righe di processi diversi non si mescolano mai.

## 1. Scenari di prova generati via codice

Tre scenari riproducibili, come chiede la consegna, ognuno con una `source` e un `backup` (la
destinazione com'era all'ultima sincronizzazione):

| scenario | file | struttura | dimensione |
| --- | --- | --- | --- |
| `few_files` | 10 | una cartella | 18 MB, file da qualche MB |
| `many_files` | 5000 | una cartella | 155 MB, file piccoli |
| `nested_folders` | 2000 | 572 sottocartelle, fino a 6 livelli | 247 MB |

Il backup è costruito con uno **schema fisso e non casuale**, così tutte e tre le azioni compaiono
anche nello scenario da dieci file: un file su dieci manca, uno su dieci ha contenuto diverso e
timestamp più vecchio di un'ora, uno ogni venti è obsoleto. I file modificati hanno **la stessa
dimensione dell'originale**, apposta: un confronto sulla dimensione non li vedrebbe.

## 2. Confronto: la lista delle azioni

Per ogni percorso relativo, `copy` se il file manca in destinazione, `update` se in sorgente è più
recente, `delete` se esiste solo in destinazione. **Decide solo il timestamp**, letto in
nanosecondi interi con due chiamate a `os.stat`: il contenuto non si legge mai. Il tipo si
controlla in modo esplicito, così un file al posto di una cartella con lo stesso nome (o il
contrario) diventa una copia e non un errore.

Il confronto è affidato ai **processi**: oltre a `os.stat`, che rilascia il GIL, c'è il lavoro
dell'interprete — costruire percorsi, confrontare, raccogliere — e solo processi distinti lo
eseguono davvero in parallelo. I file sono distribuiti fra i worker **a rotazione** e non per
cartella, così piccoli e grandi si spartiscono in modo uniforme.

## 3. Esecuzione delle azioni

L'esecuzione è affidata ai **thread**: una copia aspetta il disco o la rete, e durante l'attesa il
GIL è libero per la copia successiva. Le azioni girano in **due turni**: prima le rimozioni, poi
la pulizia delle cartelle rimaste vuote, infine copie e aggiornamenti — come `rsync
--delete-before`. È ciò che impedisce a un file e a una cartella con lo stesso nome di incontrarsi.
Ogni file ha il suo blocco `try`: un errore viene raccolto e il ciclo prosegue.

`copy2` copia anche il timestamp, quindi dopo la sincronizzazione "uguale" significa "stessa
versione", e la regola *più recente in sorgente* confronta due versioni e non una versione con
una data di copia.

## 4. Il motore completo e la verifica

`sync_folders(source_folder, destination_folder)` riunisce le due fasi. La correttezza è provata
con due `assert` indipendenti su ogni scenario:

- **contenuto** — l'MD5 di ogni file in destinazione coincide con quello della sorgente;
- **nessun residuo** — un secondo confronto non trova più nessuna azione.

Entrambe passano: 500 copie, 500 aggiornamenti e 250 rimozioni con molti file, 200/200/100 con le
sottocartelle, più **142 cartelle rimaste vuote rimosse**. Una prova aggiuntiva costruisce il caso
che i tre scenari non contengono — `reports` da file a cartella, `notes` da cartella a file — e il
motore lo risolve senza errori grazie ai due turni.

Le impronte MD5 le calcola il codice di prova, non il motore: dentro il confronto avrebbero
obbligato a leggere ogni file, e i tempi della sezione 6 avrebbero misurato la prova insieme alla
sincronizzazione.

## 5. Errori sui file e sulle cartelle

Due regole opposte, ed entrambe sono una scelta:

- **un file che sparisce fra confronto ed esecuzione** fa fallire solo la propria azione: 1249
  azioni su 1250 eseguite, l'errore riportato a fine esecuzione e nel log a livello `ERROR`;
- **una coppia di cartelle sbagliata ferma tutto** prima di elencare un file. Il motivo è concreto:
  `os.walk` su una sorgente inesistente restituisce un elenco vuoto senza errori, e il confronto
  pianificherebbe la rimozione di **tutti i 4750 file** della destinazione. `check_folders`
  rifiuta sorgente mancante, sorgente che è un file, destinazione che è un file e cartelle
  sovrapposte.

Con `dry_run=True` il motore restituisce la lista senza eseguirla. Sono tre righe, perché la lista
esiste comunque prima dell'esecuzione.

## 6. Misura dei tempi

Ogni fase misurata in tre modalità (sequenziale, thread, processi), migliore di cinque ripetizioni,
destinazione ricreata prima di ognuna. Il risultato **contraddice in parte le scelte delle sezioni
2 e 3**, e il notebook lo dichiara invece di nasconderlo:

| | confronto | esecuzione |
| --- | --- | --- |
| **pochi file** | thread e processi più lenti | processi circa 20 volte più lenti |
| **molti file** | processi alla pari, thread più lenti | processi meglio (~1,3×), thread più lenti |
| **sottocartelle** | processi alla pari, thread più lenti | tutto vicino alla parità |

Le cause, in ordine di peso:

- **legge di Amdahl** — l'elenco dei due alberi resta nel processo principale e occupa circa
  **tre quarti** del confronto sequenziale: nessuna modalità può dividere quella parte;
- **lavoro per file troppo leggero** — due `os.stat` non ripagano l'avvio di un interprete;
- **disco servito dalla cache** — i file appena scritti stanno in memoria, la copia non aspetta
  quasi mai il disco e i thread non hanno attese da sovrapporre;
- **overhead dei processi** — con dieci file avviarli costa più di tutto il lavoro: è l'effetto che
  la consegna chiedeva di mostrare.

La sincronizzazione completa con la combinazione scelta (processi + thread) resta vicina alla
parità sugli scenari grandi ed è molto più lenta con pochi file. I tempi sono di millisecondi o
decimi di secondo e cambiano a ogni esecuzione: il testo riporta **il verso dei confronti, non le
cifre**.

## 7. Conclusioni e raccomandazioni

Il motore è corretto sui tre scenari e sul conflitto di nomi, un file non disponibile non lo ferma,
una coppia di cartelle sbagliata sì. Sul fronte prestazionale le raccomandazioni al team
infrastruttura sono quattro:

- **cartelle piccole** → tutto sequenziale; la soglia sta fra dieci e qualche migliaio di file e
  non è stata misurata. Le modalità sono parametri di `sync_folders`, cambiarle non tocca il codice;
- **destinazione nuova** → prima esecuzione con `dry_run=True`, per controllare le rimozioni;
- **destinazione di rete o cloud** → thread per l'esecuzione, in numero scelto sulla latenza reale
  e non sulle CPU;
- **disco locale con molti file piccoli** → processi anche per l'esecuzione, confronto sequenziale.

## 8. Approfondimento oltre la consegna: destinazione con latenza

Se su disco locale i thread non accelerano, la scelta della sezione 3 va giustificata altrove.
Si simula una destinazione remota con un'attesa fissa di **2 ms** prima di ogni scrittura, e si
scrive la previsione **prima** di misurare: se i thread guadagnano grazie alle CPU si fermano
vicino a 2, se sovrappongono le attese si avvicinano a 8.

Esito sullo scenario con molti file: **thread circa 6× più veloci del sequenziale, processi circa
2×**. Otto thread tengono aperte otto attese insieme, due processi solo due. È questo risultato a
giustificare i thread come default per l'esecuzione: su un backup remoto sono di gran lunga la
modalità migliore.

---

## Note di progetto — scelte e limiti dichiarati

**Scelte:**

1. **Confronto ed esecuzione separati** — la lista si controlla, si divide in sottogruppi e si può
   non eseguire. Prezzo: fra le due fasi un file può cambiare, ed è gestito come errore di quel file.
2. **Il timestamp decide, l'impronta verifica** — un hash leggerebbe per intero anche la
   destinazione, costoso su un backup remoto. L'MD5 resta nel codice di prova.
3. **Cartelle controllate prima del confronto** — l'unico errore che ferma tutto, perché una
   sorgente mancante non ne produce nessuno. Prezzo: una cartella di rete irraggiungibile per poco
   fa saltare l'intera sincronizzazione.
4. **Rimozioni prima delle copie** — risolve i conflitti fra file e cartelle omonimi. Prezzo: i
   worker si avviano due volte.
5. **Processi per il confronto, thread per l'esecuzione** — tenuti come default anche se su disco
   locale non sono i più veloci, perché sono quelli giusti verso una destinazione che aspetta.
6. **Sottogruppi a rotazione** — dividere per cartella darebbe tutto a un worker quando i file
   stanno in una cartella sola.
7. **Log scritto solo dal processo principale** — niente code condivise fra processi. Prezzo: il
   log di una fase arriva a fase conclusa.
8. **`fork` dichiarato esplicitamente** — da Python 3.14 il default su Linux cambia, e con `spawn`
   i figli non vedrebbero le funzioni definite nel notebook.

**Limiti:**

1. **Una sola macchina** — 2 CPU e disco in cache; altrove i rapporti cambiano.
2. **Si propaga solo la sorgente più recente** — un file modificato a mano in destinazione non viene
   riallineato, e gli orologi delle due macchine devono essere coerenti.
3. **Il motore non verifica le proprie copie** — una copia corrotta prende comunque il timestamp
   della sorgente e ai passaggi successivi risulta aggiornata.
4. **Solo file regolari** — cartelle vuote della sorgente, link simbolici e permessi non sono gestiti.
5. **Non funziona su Windows** — lì esiste solo `spawn`: il motore andrebbe spostato in un modulo
   `.py` importabile e lanciato sotto `if __name__ == "__main__":`.
6. **Misure con il GIL attivo** — sulla build free-threaded di Python 3.13+ il confronto fra thread
   e processi andrebbe rifatto da capo.
