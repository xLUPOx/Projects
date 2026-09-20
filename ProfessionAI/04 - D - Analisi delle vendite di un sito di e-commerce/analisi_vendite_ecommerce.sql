/*
XYZ E-commerce - analisi delle vendite
======================================

Lo script risponde alle cinque fasi della consegna interrogando le tabelle `prodotto`,
`cliente` e `ordini`: dataset integrato, spesa per cliente, fatturato per prodotto,
fatturato medio per giorno della settimana, prodotti per ordine.

Ogni sezione è una query autonoma seguita dal proprio risultato in un blocco commentato.

Sezioni:
  1. PREPARAZIONE DEI DATI    dataset integrato dalle tre tabelle
  2. ANALISI DEI CLIENTI      spesa totale e top spender
  3. ANALISI DEI PRODOTTI     fatturato per prodotto e best-seller
  4. ANALISI TEMPORALE        fatturato medio per giorno della settimana
  5. ANALISI DEGLI ORDINI     media e distribuzione dei prodotti per ordine

Requisiti: SQLite 3. I risultati riportati sotto ogni query vengono da quel motore, dove
tutte e cinque le sezioni girano senza modifiche.

Dati: lo script di creazione indicato dalla consegna, che crea e popola le tre tabelle.
Qui è chiamato `ecommerce.sql` ed è scaricabile da
https://raw.githubusercontent.com/Profession-AI/progetti-sql/refs/heads/main/Analisi%20delle%20vendite%20di%20un%20sito%20di%20e-commerce/ecommerce.sql

Uso: da una cartella che contiene questo file e `ecommerce.sql`.

  1. Client da riga di comando, in un ambiente virtuale per non installarlo a sistema:
       py -m venv venv
       .\venv\Scripts\Activate.ps1
       pip install litecli

  2. Creazione del database e caricamento delle tabelle:
       Get-Content ecommerce.sql | litecli --no-warn --table ecommerce.db

  3. Esecuzione dell'analisi:
       Get-Content "compito analisi vendite ecommerce.sql" | litecli --no-warn --table ecommerce.db
     
     `--no-warn` serve perché l'ingresso arriva da un file e non dalla tastiera, 
     `--table` stampa i risultati nella stessa forma dei blocchi riportati sotto ogni query.    

Al fondo: NOTE DI PROGETTO
*/


-- --------------------------------------------------------------------------
-- SEZIONE 1 - PREPARAZIONE DEI DATI
-- --------------------------------------------------------------------------

-- uniamo le tre tabelle nel dataset integrato richiesto dalla consegna
-- Il join è INNER su entrambi i lati: una riga di `ordini` con chiavi esterne che non
-- risolvono gonfierebbe tutti i totali calcolati dopo.
SELECT
    o.data      AS order_date,
    c.id        AS customer_id,
    c.email     AS customer_email,
    p.nome      AS product_name,
    p.prezzo    AS unit_price
FROM ordini o
JOIN cliente  c ON c.id = o.id_cliente
JOIN prodotto p ON p.id = o.id_prodotto
ORDER BY o.data, c.id;

/* Risultato (prime 6 righe delle 20 totali):

   +------------+-------------+--------------------------+----------------------+------------+
   | order_date | customer_id | customer_email           | product_name         | unit_price |
   +------------+-------------+--------------------------+----------------------+------------+
   | 2025-01-01 | 1           | mario.rossi@example.com  | Smartphone           | 699.99     |
   | 2025-01-02 | 1           | mario.rossi@example.com  | Laptop               | 1099.99    |
   | 2025-01-03 | 2           | luigi.verdi@example.com  | Auricolari Bluetooth | 49.99      |
   | 2025-01-04 | 3           | anna.bianchi@example.com | Monitor 4K           | 299.99     |
   | 2025-01-05 | 4           | carla.neri@example.com   | Mouse Wireless       | 19.99      |
   | 2025-01-06 | 5           | giulia.ferri@example.com | Tastiera Meccanica   | 89.99      |
   +------------+-------------+--------------------------+----------------------+------------+

   Il dataset integrato conta 20 righe su 10 prodotti e 5 clienti, dal 2025-01-01 al
   2025-01-20. Nel join non si perde nessuna riga, quindi ogni chiave esterna risolve.

   `ordini` non ha una colonna quantità: ogni riga vale un pezzo e il prezzo del prodotto
   è il valore della riga. Non ha nemmeno un identificativo d'ordine, e la sezione 5 dovrà
   ricostruirlo.
*/


-- --------------------------------------------------------------------------
-- SEZIONE 2 - ANALISI DEI CLIENTI
-- --------------------------------------------------------------------------

-- sommiamo i prezzi dei prodotti acquistati da ogni cliente e ordiniamo per spesa totale
-- ROUND necessario: SQLite non ha il tipo DECIMAL e somma in virgola mobile, quindi
-- senza arrotondamento la spesa di due clienti leggerebbe 499.96000000000004.
SELECT
    c.id                        AS customer_id,
    c.email                     AS customer_email,
    COUNT(*)                    AS items_bought,
    ROUND(SUM(p.prezzo), 2)     AS total_spent,
    ROUND(100.0 * SUM(p.prezzo) / (
        SELECT SUM(p2.prezzo) FROM ordini o2
        JOIN prodotto p2 ON p2.id = o2.id_prodotto), 1) AS share_pct
FROM ordini o
JOIN cliente  c ON c.id = o.id_cliente
JOIN prodotto p ON p.id = o.id_prodotto
GROUP BY c.id, c.email
ORDER BY total_spent DESC;

/* Risultato (5 righe):

   +-------------+--------------------------+--------------+-------------+-----------+
   | customer_id | customer_email           | items_bought | total_spent | share_pct |
   +-------------+--------------------------+--------------+-------------+-----------+
   | 1           | mario.rossi@example.com  | 5            | 3899.95     | 50.1      |
   | 3           | anna.bianchi@example.com | 4            | 2199.96     | 28.3      |
   | 5           | giulia.ferri@example.com | 3            | 879.97      | 11.3      |
   | 2           | luigi.verdi@example.com  | 4            | 499.96      | 6.4       |
   | 4           | carla.neri@example.com   | 4            | 299.96      | 3.9       |
   +-------------+--------------------------+--------------+-------------+-----------+

   La somma della colonna dà il fatturato del periodo, 7779,80 euro. Il top spender è
   mario.rossi@example.com, che da solo vale il 50,1% del totale.

   La classifica non segue il numero di articoli: Luigi Verdi e Carla Neri ne hanno
   comprati 4 come Anna Bianchi, ma spendono molto meno. È il prezzo medio del carrello a
   separare i clienti, non la frequenza d'acquisto.
*/


-- --------------------------------------------------------------------------
-- SEZIONE 3 - ANALISI DEI PRODOTTI
-- --------------------------------------------------------------------------

-- calcoliamo il fatturato per prodotto, con le unità vendute accanto al totale
-- ROUND per lo stesso motivo della sezione 2: le somme sono in virgola mobile.
SELECT
    p.id                        AS product_id,
    p.nome                      AS product_name,
    p.prezzo                    AS unit_price,
    COUNT(*)                    AS units_sold,
    ROUND(SUM(p.prezzo), 2)     AS total_revenue,
    ROUND(100.0 * SUM(p.prezzo) / (
        SELECT SUM(p2.prezzo) FROM ordini o2
        JOIN prodotto p2 ON p2.id = o2.id_prodotto), 1) AS share_pct
FROM ordini o
JOIN prodotto p ON p.id = o.id_prodotto
GROUP BY p.id, p.nome, p.prezzo
ORDER BY total_revenue DESC;

/* Risultato (10 righe):

   +------------+----------------------+------------+------------+---------------+-----------+
   | product_id | product_name         | unit_price | units_sold | total_revenue | share_pct |
   +------------+----------------------+------------+------------+---------------+-----------+
   | 2          | Laptop               | 1099.99    | 2          | 2199.98       | 28.3      |
   | 9          | Fotocamera DSLR      | 799.99     | 2          | 1599.98       | 20.6      |
   | 1          | Smartphone           | 699.99     | 2          | 1399.98       | 18.0      |
   | 7          | Tablet               | 499.99     | 2          | 999.98        | 12.9      |
   | 4          | Monitor 4K           | 299.99     | 2          | 599.98        | 7.7       |
   | 8          | Smartwatch           | 199.99     | 2          | 399.98        | 5.1       |
   | 10         | Stampante            | 129.99     | 2          | 259.98        | 3.3       |
   | 6          | Tastiera Meccanica   | 89.99      | 2          | 179.98        | 2.3       |
   | 3          | Auricolari Bluetooth | 49.99      | 2          | 99.98         | 1.3       |
   | 5          | Mouse Wireless       | 19.99      | 2          | 39.98         | 0.5       |
   +------------+----------------------+------------+------------+---------------+-----------+

   Il best-seller per fatturato è il Laptop con 2199,98 euro, il 28,3% del totale secondo
   `share_pct`.

   La colonna `units_sold` mostra però che tutti i prodotti hanno venduto 2 unità: con
   quantità costanti la classifica per fatturato coincide con quella per prezzo, e non
   dice nulla sulle preferenze dei clienti.
*/


-- --------------------------------------------------------------------------
-- SEZIONE 4 - ANALISI TEMPORALE
-- --------------------------------------------------------------------------

-- aggreghiamo per giorno della settimana, dividendo il fatturato per le date osservate
-- strftime('%w') restituisce il giorno come cifra, 0 per la domenica, e `weekdays` la
-- traduce in nome. ROUND serve perché la divisione non è esatta, e `total_revenue` decide
-- fra sabato e martedì, che pareggiano a 399.99.
WITH weekdays(dow, weekday_name) AS (
    SELECT '0', 'Sunday'    UNION ALL SELECT '1', 'Monday' UNION ALL
    SELECT '2', 'Tuesday'   UNION ALL SELECT '3', 'Wednesday' UNION ALL
    SELECT '4', 'Thursday'  UNION ALL SELECT '5', 'Friday' UNION ALL
    SELECT '6', 'Saturday'
)
SELECT
    w.weekday_name                                          AS weekday_name,
    COUNT(DISTINCT o.data)                                  AS days_observed,
    ROUND(SUM(p.prezzo), 2)                                 AS total_revenue,
    ROUND(SUM(p.prezzo) / COUNT(DISTINCT o.data), 2)        AS avg_daily_revenue
FROM ordini o
JOIN prodotto p ON p.id = o.id_prodotto
JOIN weekdays w ON w.dow = strftime('%w', o.data)
GROUP BY w.dow, w.weekday_name
ORDER BY avg_daily_revenue DESC, total_revenue DESC;

/* Risultato (7 righe):

   +--------------+---------------+---------------+-------------------+
   | weekday_name | days_observed | total_revenue | avg_daily_revenue |
   +--------------+---------------+---------------+-------------------+
   | Thursday     | 3             | 1989.97       | 663.32            |
   | Sunday       | 3             | 1919.97       | 639.99            |
   | Saturday     | 3             | 1199.97       | 399.99            |
   | Tuesday      | 2             | 799.98        | 399.99            |
   | Wednesday    | 3             | 919.97        | 306.66            |
   | Friday       | 3             | 679.97        | 226.66            |
   | Monday       | 3             | 269.97        | 89.99             |
   +--------------+---------------+---------------+-------------------+

   Il giorno con la media più alta è il giovedì con 663,32 euro, seguito dalla domenica
   con 639,99.

   La colonna `days_observed` ridimensiona il risultato: ogni giorno compare 2 o 3 volte e
   ogni data porta un solo acquisto. Il giovedì vince perché il 2025-01-02 è stato venduto
   il Laptop, e il vantaggio sulla domenica è di 23,33 euro.

   Con 2 o 3 osservazioni per giorno la classifica non è statisticamente significativa e
   non va usata per decidere: misura quale prodotto è capitato in quale data, non una
   preferenza settimanale dei clienti.
*/


-- --------------------------------------------------------------------------
-- SEZIONE 5 - ANALISI DEGLI ORDINI
-- --------------------------------------------------------------------------

-- verifichiamo se la coppia (id_cliente, data) possa raggruppare più di una riga
-- Se la media di 1,0 fosse un artefatto del raggruppamento, qualche coppia conterrebbe due
-- righe e comparirebbe qui: la query non ne restituisce nessuna, quindi il valore viene
-- dai dati.
SELECT id_cliente, data, COUNT(*) AS rows_in_group
FROM ordini
GROUP BY id_cliente, data
HAVING COUNT(*) > 1;

/* Risultato: nessuna riga.

   Nessun cliente ha acquistato due volte nello stesso giorno, quindi ogni riga di `ordini`
   è già un ordine a sé e la media della query seguente vale 1,0 per i dati, non per la
   definizione scelta.
*/


-- ricostruiamo gli ordini per cliente e data, poi ne calcoliamo la media
-- La coppia (id_cliente, data) fa da chiave surrogata: la tabella non ha un identificativo
-- d'ordine, quindi un ordine è ciò che un cliente ha comprato in una giornata.
WITH orders AS (
    SELECT id_cliente, data, COUNT(*) AS items_per_order
    FROM ordini
    GROUP BY id_cliente, data
)
SELECT
    COUNT(*)                            AS orders_total,
    ROUND(AVG(items_per_order), 2)      AS avg_items_per_order,
    MIN(items_per_order)                AS min_items_per_order,
    MAX(items_per_order)                AS max_items_per_order
FROM orders;

/* Risultato (1 riga):

   +--------------+---------------------+---------------------+---------------------+
   | orders_total | avg_items_per_order | min_items_per_order | max_items_per_order |
   +--------------+---------------------+---------------------+---------------------+
   | 20           | 1.0                 | 1                   | 1                   |
   +--------------+---------------------+---------------------+---------------------+
*/

-- misuriamo la distribuzione, cioè quanti ordini esistono per ogni numero di prodotti
WITH orders AS (
    SELECT id_cliente, data, COUNT(*) AS items_per_order
    FROM ordini
    GROUP BY id_cliente, data
)
SELECT
    items_per_order,
    COUNT(*)    AS orders_count
FROM orders
GROUP BY items_per_order
ORDER BY items_per_order;

/* Risultato (1 riga):

   +-----------------+--------------+
   | items_per_order | orders_count |
   +-----------------+--------------+
   | 1               | 20           |
   +-----------------+--------------+

   Gli ordini ricostruiti sono 20 e la media è 1,0 prodotti per ordine. La distribuzione
   ha una sola classe: tutti gli ordini contengono un solo prodotto, e minimo e massimo
   coincidono con la media.

   La causa sta nei dati: nessun cliente ha comprato due volte nello stesso giorno, quindi
   ogni riga è già un ordine a sé.
*/


/*
NOTE DI PROGETTO
===========================================

Scelte
------

1. L'ordine è ricostruito dalla coppia (id_cliente, data).
   `ordini` non ha un identificativo d'ordine, quindi la sezione 5 definisce come ordine
   ciò che un cliente ha comprato in una giornata. L'alternativa, raggruppare per solo
   cliente, misurerebbe il totale storico e duplicherebbe la sezione 2. La query di
   controllo in testa alla sezione 5 mostra che qui nessuna coppia raggruppa più di una
   riga, quindi la media di 1,0 viene dai dati. Il limite noto è che su dati diversi due
   acquisti dello stesso cliente nello stesso giorno risulterebbero come un ordine solo.

2. Le unità vendute sono selezionate accanto al fatturato.
   È una colonna in più rispetto al minimo richiesto, ma senza di essa la classifica della
   sezione 3 sembrerebbe una graduatoria di popolarità. Il limite noto è che su un catalogo
   con quantità variabili le due colonne possono ordinare in modo discorde.

3. La media giornaliera divide per le date osservate, non per le righe.
   Dividere per il numero di righe darebbe il prezzo medio di un acquisto e non il
   fatturato di una giornata. Il limite noto è che le giornate senza ordini non compaiono
   nella tabella e quindi restano fuori dalla media.

4. Lo script è scritto per SQLite.
   La consegna non impone un motore, e su SQLite `ecommerce.sql` si carica senza modifiche.
   L'alternativa, `DAYNAME` di MySQL, darebbe il nome del giorno in una sola espressione ma
   legherebbe il file a quel motore. Il limite noto è che anche `strftime` è specifico di
   SQLite, quindi portare altrove la sezione 4 significa sostituirlo.

5. Gli importi sono arrotondati a due decimali con ROUND.
   SQLite somma i prezzi in virgola mobile, e senza arrotondamento comparirebbero code come
   499.96000000000004. Il limite noto è che l'arrotondamento avviene alla lettura: le somme
   restano in virgola mobile, e su volumi maggiori servirebbe un tipo esatto.
*/
