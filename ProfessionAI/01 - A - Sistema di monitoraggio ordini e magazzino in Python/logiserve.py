"""
LogiServe S.r.l. - Sistema di monitoraggio ordini e magazzino
============================================================

Applicativo a riga di comando che simula il gestionale di magazzino di
LogiServe S.r.l., piccola realtà di e-commerce B2B che distribuisce
componenti elettrici a officine e rivenditori.

Funzionalita' principali:
  1. Registrazione di nuovi ordini con verifica immediata della
     disponibilità (disponibile / parziale / indisponibile).
  2. Evasione degli ordini con aggiornamento automatico delle giacenze
     e gestione degli stati "parziale" e "in attesa". Quando la merce non
     basta per tutti conta la sequenza di evasione: prima gli ordini
     urgenti e, a parità di urgenza, quelli con la data più vecchia.
     Gli ordini aperti sono elencati in quella sequenza e scavalcarla
     resta possibile, ma il programma dice chi si sta superando e chiede
     conferma.
  3. Carico e rettifica manuale del magazzino per lotti d'acquisto interi
     (es. bobine da 100 m), secondo la dimensione del lotto definita per
     ogni prodotto.
  4. Consultazione in tempo reale del magazzino, con filtri per codice,
     categoria o soglia di riordino.
  5. Report giornaliero sintetico (ordini ricevuti, evasi, in sospeso,
     prodotti più venduti, variazione giacenze) esportato su file di testo.
  6. Persistenza dello stato su file JSON/CSV: al riavvio il programma
     ricarica catalogo e ordini; lo storico operazioni prosegue sullo
     stesso file e viene riletto dal report quando serve.
  7. Tracciabilita': ogni operazione viene registrata su un file di log
     con timestamp e nome operatore.

Architettura presente nello script:
  - PERSISTENCE   caricamento/salvataggio dei file di dati
  - LOGGING       storico delle operazioni
  - WAREHOUSE     catalogo prodotti e giacenze
  - ORDERS        registrazione ed evasione degli ordini
  - REPORTING     report giornaliero ed esportazione
  - UI HELPERS    validazione input, tasti globali, controlli sui typo
  - UI ACTIONS    una funzione per ogni voce di menu
  - MAIN LOOP     menu testuale e gestione dei comandi

Istruzioni per l'uso:
  $ python logiserve.py      (su Windows: py logiserve.py)
  Alla prima esecuzione i file di dati vengono creati automaticamente
  nella cartella "data/" con dati di esempio simulati, storico incluso.

  Al menu e ad ogni domanda del programma valgono tre tasti:
    ?  spiega l'operazione in corso e cosa è richiesto in quel passaggio
    h  annulla l'operazione e torna al menu principale
    q  salva tutto ed esce
  Per scegliere un prodotto non serve conoscere i codici: basta digitare
  parte del nome o della categoria e selezionare dalla lista proposta.

Requisiti: Python 3.8+ (solo libreria standard).

Al fondo: NOTE DI PROGETTO - scelte, semplificazioni e sviluppi futuri
"""

import csv
import difflib
import json
import os
from datetime import datetime

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------

DATA_DIR = "data"
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
LOG_FILE = os.path.join(DATA_DIR, "operations_log.csv")

# Name written in the log when the operator does not type one, and author
# of the example data created on the first run.
DEFAULT_OPERATOR = "Operatore Test"

# Order statuses
STATUS_NEW = "new"
STATUS_PARTIAL = "partial"
STATUS_FULFILLED = "fulfilled"

# Fulfillment priorities. They are values of the data exactly like the
# statuses above, so they are named here and not written by hand.
PRIORITY_HIGH = "high"
PRIORITY_NORMAL = "normal"

# Names of the logged operations. Only OP_STOCK_UPDATE is read back, by the
# daily report, so a typo there would silently make it count nothing; the
# others are written for whoever reads the log, and are named here to keep
# the file consistent with itself.
OP_ORDER_NEW = "ORDER_NEW"
OP_ORDER_FULFILL = "ORDER_FULFILL"
OP_STOCK_UPDATE = "STOCK_UPDATE"
OP_SESSION_START = "SESSION_START"
OP_SESSION_END = "SESSION_END"

# Causes of a stock movement, written by change_stock and read back by
# parse_movement. The report compares the cause with MOVEMENT_ORDER to tell
# goods sold from goods loaded: MOVEMENT_MANUAL is the case that is left.
MOVEMENT_ORDER = "order"
MOVEMENT_MANUAL = "manual"

# Dates are written, read and validated with this single format: order
# dates, fulfillment dates and the name of the exported report.
DATE_FORMAT = "%Y-%m-%d"

# How many products the daily report lists as the best selling ones: enough
# to see what is moving, few enough to stay a summary.
TOP_PRODUCTS = 5

BANNER = """
+-------------------------------------------------------+
|  LOGISERVE S.r.l.                                     |
|  Orders & Warehouse Monitor                           |
+-------------------------------------------------------+
"""

SEPARATOR = "=" * 72

# Keys accepted at every single question of the program.
KEYS_HINT = "? = help on this step   h = back to menu   q = save and quit"

HELP_TEXT = """
Available commands (type the number or the keyword):

  1 | order          Register a new order
  2 | fulfill        Fulfill an order, urgent first (updates stock)
  3 | warehouse [x]  Show the warehouse; the optional text filters it
  4 | stock          Load/remove stock of a product, in purchase lots
  5 | orders         List all registered orders
  6 | report         Build the daily report and export it to a file
  ? | help           Show this help text
  q | quit           Save everything and exit

Notes:
  - You never need to know the product codes by heart: when a product is
    requested you can type a code, a piece of the name or of the category
    (e.g. "led", "cavo"), and pick from the list of matches.
  - Everything is case-insensitive; on a typo the closest match is suggested.
  - At the menu, "h", "menu" and "back" all just show the prompt again.
  - Only "warehouse" reads the text typed after the command.
  - Data is saved automatically after every operation in "data/".
"""

# Title shown when an action starts: it tells the operator where they are.
ACTION_TITLES = {
    "order": "NEW ORDER",
    "fulfill": "FULFILL ORDER",
    "warehouse": "WAREHOUSE STATUS",
    "stock": "STOCK ADJUSTMENT",
    "orders": "ORDER LIST",
    "report": "DAILY REPORT",
    "help": "HELP",
}

# Text printed by "?" inside each action: what this step is for and what
# the operator is expected to do here. One entry per command of
# ACTION_TITLES, plus "menu" for the main prompt.
CONTEXT_HELP = {
    "menu": HELP_TEXT,
    "order": """
  NEW ORDER - you are registering an order received from a customer.
  You will be asked, in this order: the customer name, the order date
  (Enter proposes today's date and asks you to confirm it), the priority
  (0 normal, 1 high), then one line per product.
  For every line: pick the product, then type the quantity requested.
  Leave the product empty to close the order.
  Nothing is written until the order is complete: 'h' cancels everything.
  At the end the system tells you whether the order is AVAILABLE, PARTIAL
  or UNAVAILABLE; the stock is not touched yet, that happens on 'fulfill'.
""",
    "fulfill": """
  FULFILL ORDER - you are shipping the goods of an order already registered.
  Pick an order from the numbered list (or type its id, e.g. ORD-0002).
  The list is the sequence the orders should be shipped in: the urgent
  ones first and, at equal priority, the oldest order date first. Picking
  anything but the first one overtakes the orders above it, so the system
  names them and asks you to confirm.
  The system ships every line as far as the stock allows, then sets the
  order to 'fulfilled' (all shipped), 'partial' (something shipped) or it
  leaves it 'new' (nothing available). Stock is reduced here, and at the
  end every product of the catalog that is at or below its reorder point
  is listed, not only the ones shipped with this order.
""",
    "warehouse": """
  WAREHOUSE STATUS - read-only view of the current stock.
  'warehouse' alone shows every product; 'warehouse cavi' filters by code,
  name or category; 'warehouse low', or 'warehouse reorder', shows only the
  products that are at or below their reorder point.
  REORDER!/OUT OF STOCK! flag what to restock,
  and the LOT column is the size of the lot they are bought in.
""",
    "stock": """
  STOCK ADJUSTMENT - manual correction of a product stock, used when goods
  arrive from a supplier or after an inventory check.
  Products are bought in lots (a 100 m reel of cable, a box of 4 lamps),
  so you do not type units here: pick the product, read the lot size shown
  on screen, then type how many LOTS to load (e.g. 2) or to remove (-1).
  The units are computed for you and the stock can never go below zero.
  The operation is written to the log with your name.
""",
    "orders": """
  ORDER LIST - read-only list of every order with its status and lines.
  The [n] after each line is how many units have already been shipped.
  Under each order you find who registered it and, if it has been shipped,
  who fulfilled it and when: the same names written to the operations log.
""",
    "help": HELP_TEXT,
    "report": """
  DAILY REPORT - summary of one day of activity.
  Type the date, or press Enter and confirm today's. The report counts the
  orders received and fulfilled on that day and lists its best selling
  products and stock movements; the orders still open, split between
  urgent and normal, and the products to restock are instead the situation
  of today, as their labels say.
  It is printed here and exported to data/report_<date>.txt to be shared
  internally.
""",
}

# --------------------------------------------------------------------------
# SEED DATA (used only the first time, when data files do not exist yet)
# --------------------------------------------------------------------------

# "stock" is the stock available now, not the one the warehouse started
# from: it is already net of the units shipped with ORD-0001 in SEED_LOG
# (EL-1001 started at 150 and IN-2001 at 50).
SEED_CATALOG = [
    {"code": "EL-1001", "name": "Cavo unipolare 2.5mm", "category": "Cavi",
     "stock": 120, "reorder_point": 40, "unit": "m", "lot_size": 100},
    {"code": "EL-1002", "name": "Cavo multipolare 3x1.5mm", "category": "Cavi",
     "stock": 60, "reorder_point": 30, "unit": "m", "lot_size": 100},
    {"code": "IN-2001", "name": "Interruttore magnetotermico 16A", "category": "Interruttori",
     "stock": 45, "reorder_point": 20, "unit": "pz", "lot_size": 6},
    {"code": "IN-2002", "name": "Differenziale 25A", "category": "Interruttori",
     "stock": 18, "reorder_point": 20, "unit": "pz", "lot_size": 6},
    {"code": "QD-3001", "name": "Quadro da parete 12 moduli", "category": "Quadri",
     "stock": 12, "reorder_point": 5, "unit": "pz", "lot_size": 1},
    {"code": "IL-4001", "name": "Plafoniera LED 36W", "category": "Illuminazione",
     "stock": 8, "reorder_point": 15, "unit": "pz", "lot_size": 4},
    {"code": "IL-4002", "name": "Faretto LED 10W", "category": "Illuminazione",
     "stock": 200, "reorder_point": 50, "unit": "pz", "lot_size": 10},
]

# Every order carries the operator who registered it and the one who
# fulfilled it: the same information written to the log must survive in the
# data itself, otherwise it would only exist in the history file.
SEED_ORDERS = [
    {"id": "ORD-0001", "date": "2026-07-30", "customer": "Officina Rossi",
     "priority": PRIORITY_NORMAL, "status": STATUS_FULFILLED,
     "registered_by": DEFAULT_OPERATOR,
     "fulfilled_date": "2026-07-30", "fulfilled_by": DEFAULT_OPERATOR,
     "lines": [{"code": "EL-1001", "qty": 30, "shipped": 30},
               {"code": "IN-2001", "qty": 5, "shipped": 5}]},
    {"id": "ORD-0002", "date": "2026-07-31", "customer": "Elettro Bianchi",
     "priority": PRIORITY_HIGH, "status": STATUS_NEW,
     "registered_by": DEFAULT_OPERATOR,
     "fulfilled_date": None, "fulfilled_by": None,
     "lines": [{"code": "IL-4001", "qty": 20, "shipped": 0}]},
]

# History of the example orders above. Without it the report of a past day
# would count a fulfilled order with no goods leaving the warehouse, since
# the sold quantities and the stock variations are rebuilt from the log.
# The operator of the example data is DEFAULT_OPERATOR, the same name
# proposed at start-up when no operator is typed.
SEED_LOG = [
    ["2026-07-30T09:12:00", OP_ORDER_NEW, "ORD-0001",
     "customer=Officina Rossi, availability=available", DEFAULT_OPERATOR],
    ["2026-07-30T09:40:00", OP_STOCK_UPDATE, "EL-1001", "-30 (order ORD-0001)", DEFAULT_OPERATOR],
    ["2026-07-30T09:40:00", OP_STOCK_UPDATE, "IN-2001", "-5 (order ORD-0001)", DEFAULT_OPERATOR],
    ["2026-07-30T09:40:00", OP_ORDER_FULFILL, "ORD-0001",
     "status=fulfilled, units shipped=35", DEFAULT_OPERATOR],
    ["2026-07-31T08:05:00", OP_ORDER_NEW, "ORD-0002",
     "customer=Elettro Bianchi, availability=partial", DEFAULT_OPERATOR],
]


# --------------------------------------------------------------------------
# PERSISTENCE
# --------------------------------------------------------------------------

def ensure_data_dir():
    """Create the data folder if it is not there yet."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path, seed):
    """Load a JSON file; create it with seed data if it does not exist."""
    if not os.path.exists(path):
        save_json(path, seed)
        return seed
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, data):
    """Write data to a JSON file (pretty printed, UTF-8)."""
    ensure_data_dir()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def save_state(catalog, orders):
    """Persist both catalog and orders."""
    save_json(CATALOG_FILE, catalog)
    save_json(ORDERS_FILE, orders)


# --------------------------------------------------------------------------
# LOGGING
# --------------------------------------------------------------------------

LOG_HEADER = ["timestamp", "operation", "resource", "detail", "operator"]


def init_log():
    """Create the log with the history of the example data, on first run."""
    if os.path.exists(LOG_FILE):
        return
    ensure_data_dir()
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(LOG_HEADER)
        writer.writerows(SEED_LOG)


def log_operation(operation, resource, detail, operator):
    """Append one line to the operations log (CSV with header)."""
    init_log()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([datetime.now().isoformat(timespec="seconds"),
                         operation, resource, detail, operator])


def read_log():
    """Return the operations log as a list of dictionaries."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_movement(detail):
    """
    Read a stock movement back from its log detail: (delta, cause).

    The shape "<delta> (<cause> <note>)" is written by change_stock and read
    only here: the two go changed together. A line that does not have it
    gives (None, None), so an older or hand-edited log is skipped, not fatal.
    """
    delta_text, _, rest = detail.partition(" (")
    try:
        return int(delta_text), rest.split()[0].rstrip(",)")
    except (ValueError, IndexError):
        return None, None


# --------------------------------------------------------------------------
# WAREHOUSE
# --------------------------------------------------------------------------

def find_product(catalog, code):
    """
    Return the product with the given code, or None.

    None only happens for a code that does not come from the catalog, that
    is one read back from the log: the report is where it gets checked.
    """
    code = code.strip().upper()
    for product in catalog:
        if product["code"].upper() == code:
            return product
    return None


def suggest_code(catalog, code):
    """Return the closest product code to a mistyped one, or None."""
    codes = [product["code"] for product in catalog]
    return closest_match(code.strip().upper(), codes, 0.5)


def search_products(catalog, query):
    """
    Search products by code, name or category.

    The query is matched as a substring first (so "led" finds every LED
    product); if nothing matches, a fuzzy comparison on the codes catches
    typos such as "IL-4O01".
    """
    query = query.strip().lower()
    if not query:
        return []
    found = [p for p in catalog
             if query in p["code"].lower()
             or query in p["name"].lower()
             or query in p["category"].lower()]
    if found:
        return found
    suggestion = suggest_code(catalog, query)
    return [find_product(catalog, suggestion)] if suggestion else []


def print_product_list(products, title):
    """Print a numbered, compact product list used to pick a product."""
    print("  %s" % title)
    print("   %-3s %-10s %-32s %8s %5s" % ("#", "CODE", "NAME", "STOCK", "UNIT"))
    for index, product in enumerate(products, start=1):
        print("   %-3d %-10s %-32.32s %8d %5s" %
              (index, product["code"], product["name"],
               product["stock"], product["unit"]))


def needs_reorder(product):
    """
    Return True when a product is at or below its reorder point.

    Warehouse table, alerts after a fulfillment and daily report read the
    threshold from here, so that they cannot disagree on it.
    """
    return product["stock"] <= product["reorder_point"]


def change_stock(catalog, code, delta, operator, cause, note):
    """
    Apply a stock delta to a product and log the movement.

    "cause" is MOVEMENT_ORDER or MOVEMENT_MANUAL, the word the report reads
    back; "note" is the free text that follows it on the log line.
    """
    product = find_product(catalog, code)
    product["stock"] += delta
    log_operation(OP_STOCK_UPDATE, product["code"],
                  "%+d (%s %s)" % (delta, cause, note), operator)


def print_warehouse(products, below_reorder=False):
    """
    Print the warehouse table.

    Filtering by code, name or category is done by search_products before
    calling this function; only the reorder threshold is applied here,
    because it depends on a comparison between two columns.
    """
    rows = products
    if below_reorder:
        rows = [p for p in rows if needs_reorder(p)]

    if not rows:
        print("No product matches the given filters.")
        return

    header = ("%-10s %-32s %-15s %8s %8s %6s %6s  %s" %
              ("CODE", "NAME", "CATEGORY", "STOCK", "REORDER", "UNIT", "LOT", "ALERT"))
    print("\n" + header)
    print("-" * len(header))
    for product in rows:
        alert = "REORDER!" if needs_reorder(product) else ""
        if product["stock"] == 0:
            alert = "OUT OF STOCK!"
        print("%-10s %-32.32s %-15s %8d %8d %6s %6d  %s" %
              (product["code"], product["name"], product["category"],
               product["stock"], product["reorder_point"], product["unit"],
               product["lot_size"], alert))
    print("-" * len(header))
    print("%d product(s) shown.\n" % len(rows))


# --------------------------------------------------------------------------
# ORDERS
# --------------------------------------------------------------------------

def next_order_id(orders):
    """Build the next sequential order id."""
    numbers = [int(order["id"].split("-")[1]) for order in orders]
    return "ORD-%04d" % (max(numbers) + 1 if numbers else 1)


def availability_of(catalog, lines):
    """
    Classify an order as available / partial / unavailable.

    The lines are grouped by product code before the comparison: the same
    product can be asked for on more than one line, and what has to cover
    the request is the sum of those lines, not each of them on its own.
    """
    requested = {}
    for line in lines:
        requested[line["code"]] = requested.get(line["code"], 0) + line["qty"]

    full = 0
    some = 0
    for code, quantity in requested.items():
        stock = find_product(catalog, code)["stock"]
        if stock >= quantity:
            full += 1
        elif stock > 0:
            some += 1
    if full == len(requested):
        return "available"
    if full == 0 and some == 0:
        return "unavailable"
    return "partial"


def find_order(orders, order_id):
    """Return the order with the given id, or None."""
    order_id = order_id.strip().upper()
    for order in orders:
        if order["id"].upper() == order_id:
            return order
    return None


def fulfillment_sequence(orders):
    """
    Put orders in the sequence they should be shipped in.

    Urgent orders come before the normal ones and, at equal priority, the
    oldest order date first; orders of the same day keep the sequence they
    were registered in, which is what the increasing id records.
    """
    return sorted(orders, key=lambda order: (0 if order["priority"] == PRIORITY_HIGH else 1,
                                             order["date"], order["id"]))


def fulfill_order(catalog, order, operator):
    """
    Ship as much as possible of every order line.

    The order becomes "fulfilled" when every line is complete, otherwise it
    stays "partial" (some units shipped) or "new" (nothing available yet).
    """
    shipped_now = 0
    for line in order["lines"]:
        product = find_product(catalog, line["code"])
        missing = line["qty"] - line["shipped"]
        take = min(missing, product["stock"])
        if take > 0:
            change_stock(catalog, product["code"], -take, operator,
                         MOVEMENT_ORDER, order["id"])
            line["shipped"] += take
            shipped_now += take

    complete = all(line["shipped"] >= line["qty"] for line in order["lines"])
    any_shipped = any(line["shipped"] > 0 for line in order["lines"])
    if complete:
        order["status"] = STATUS_FULFILLED
    elif any_shipped:
        order["status"] = STATUS_PARTIAL
    else:
        order["status"] = STATUS_NEW

    if shipped_now > 0:
        # Who shipped the goods is stored on the order, not only in the log.
        order["fulfilled_date"] = today()
        order["fulfilled_by"] = operator
    log_operation(OP_ORDER_FULFILL, order["id"],
                  "status=%s, units shipped=%d" % (order["status"], shipped_now), operator)
    return shipped_now


def format_order_lines(order):
    """Build the summary of the lines of an order: code, quantity, shipped."""
    return ", ".join("%s x%d [%d]" % (line["code"], line["qty"], line["shipped"])
                     for line in order["lines"])


def print_orders(orders):
    """Print the list of orders with their current status."""
    if not orders:
        print("No order registered yet.")
        return
    header = ("%-10s %-12s %-22s %-10s %-8s %s" %
              ("ID", "DATE", "CUSTOMER", "STATUS", "PRIORITY", "LINES (code x qty [shipped])"))
    print("\n" + header)
    print("-" * len(header))
    for order in orders:
        lines = format_order_lines(order)
        print("%-10s %-12s %-22.22s %-10s %-8s %s" %
              (order["id"], order["date"], order["customer"],
               order["status"], order["priority"], lines))
        # Second line: who did what, kept on the order itself.
        detail = "registered by %s" % order["registered_by"]
        if order["fulfilled_by"]:
            detail += ", fulfilled by %s on %s" % (order["fulfilled_by"],
                                                   order["fulfilled_date"])
        print("%-10s %s" % ("", detail))
    print("-" * len(header) + "\n")


# --------------------------------------------------------------------------
# REPORTING
# --------------------------------------------------------------------------

def build_daily_report(catalog, orders, day):
    """
    Build the daily report text for the given day (YYYY-MM-DD).

    Orders received and fulfilled, units sold and stock movements belong
    to that day. Open orders and products to restock come from the current
    state, and carry the current date, so that no line of the report leaves
    it open which of the two days it belongs to.
    """
    received = [o for o in orders if o["date"] == day]
    fulfilled = [o for o in orders if o["fulfilled_date"] == day
                 and o["status"] == STATUS_FULFILLED]
    pending = [o for o in orders if o["status"] in (STATUS_NEW, STATUS_PARTIAL)]
    urgent = fulfillment_sequence([o for o in pending if o["priority"] == PRIORITY_HIGH])

    # Units shipped per product on that day, taken from the operations log
    # through parse_movement: the cause is compared for equality, so a note
    # that happens to contain the word "reorder" is not read as a sale.
    shipped = {}
    variations = {}
    for entry in read_log():
        if not entry["timestamp"].startswith(day) or entry["operation"] != OP_STOCK_UPDATE:
            continue
        delta, cause = parse_movement(entry["detail"])
        if delta is None:
            continue
        variations[entry["resource"]] = variations.get(entry["resource"], 0) + delta
        if cause == MOVEMENT_ORDER and delta < 0:
            shipped[entry["resource"]] = shipped.get(entry["resource"], 0) - delta

    top = sorted(shipped.items(), key=lambda item: item[1],
                 reverse=True)[:TOP_PRODUCTS]
    to_reorder = [p for p in catalog if needs_reorder(p)]

    title = "LogiServe S.r.l. - Daily report %s" % day
    out = []
    out.append(title)
    out.append("=" * len(title))
    # A day with nothing on it is a legitimate answer, but it has to say so:
    # the sections below would otherwise show today's situation under the
    # heading of a day on which nothing happened.
    if not received and not fulfilled and not variations:
        out.append("(no activity recorded on this day)")
        out.append("")
    out.append("%-30s: %d" % ("Orders received on %s" % day, len(received)))
    out.append("%-30s: %d" % ("Orders fulfilled on %s" % day, len(fulfilled)))
    out.append("%-30s: %d (%d high priority)" %
               ("Orders open as of %s" % today(), len(pending), len(urgent)))
    out.append("")
    out.append("Urgent orders open as of %s, in shipping order:" % today())
    if urgent:
        for order in urgent:
            missing = sum(line["qty"] - line["shipped"] for line in order["lines"])
            out.append("  %-10s %-22.22s of %s, %d unit(s) to ship" %
                       (order["id"], order["customer"], order["date"], missing))
    else:
        out.append("  (none)")
    out.append("")
    out.append("Top selling products on %s:" % day)
    if top:
        for code, qty in top:
            # Code read from the log: the product may be gone since.
            product = find_product(catalog, code)
            if product:
                out.append("  %-10s %-32.32s %d %s"
                           % (code, product["name"], qty, product["unit"]))
            else:
                out.append("  %-10s %-32.32s %d" % (code, "(not in the catalog)", qty))
    else:
        out.append("  (no shipment recorded on this day)")
    out.append("")
    out.append("Stock variations on %s:" % day)
    if variations:
        for code, delta in sorted(variations.items()):
            product = find_product(catalog, code)
            current = ("stock now %d" % product["stock"] if product
                       else "no longer in the catalog")
            out.append("  %-10s %+d -> %s" % (code, delta, current))
    else:
        out.append("  (no stock movement recorded on this day)")
    out.append("")
    out.append("Products at or below reorder point, stock as of %s:" % today())
    if to_reorder:
        for product in to_reorder:
            out.append("  %-10s %-32.32s stock %d (reorder %d)" %
                       (product["code"], product["name"],
                        product["stock"], product["reorder_point"]))
    else:
        out.append("  (none)")
    return "\n".join(out)


def export_report(text, day):
    """Save the report to a text file and return its path."""
    ensure_data_dir()
    path = os.path.join(DATA_DIR, "report_%s.txt" % day)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    return path


# --------------------------------------------------------------------------
# UI HELPERS (input validation, global keys and typo checks)
# --------------------------------------------------------------------------

class BackToMenu(Exception):
    """Raised when the operator types 'h' to abandon the current action."""


class QuitProgram(Exception):
    """Raised when the operator types 'q' to save and leave the program."""


# Name of the action currently running: it selects the text shown by "?".
CURRENT_CONTEXT = "menu"


def set_context(name):
    """Remember which action is running, so that '?' can explain it."""
    global CURRENT_CONTEXT
    CURRENT_CONTEXT = name


def closest_match(text, candidates, cutoff):
    """
    Return the closest candidate to a mistyped text, or None if none is near.

    Used on product codes, order ids and menu commands; the caller passes
    its own cutoff, because a wrong command costs less than a wrong code.
    """
    matches = difflib.get_close_matches(text, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def read_input(prompt, help_hook=None):
    """
    Read one answer, honoring the three keys available at every prompt:
      ?  explain the action currently running (help_hook adds the data the
         operator needs right here, e.g. the product catalog)
      h  abandon the current action and go back to the main menu
      q  save everything and quit the program
    """
    while True:
        value = input(prompt).strip()
        if value == "?":
            print(CONTEXT_HELP[CURRENT_CONTEXT])
            if help_hook:
                help_hook()
            continue
        if value.lower() == "h":
            raise BackToMenu()
        if value.lower() == "q":
            raise QuitProgram()
        return value


def ask_text(prompt, allow_empty=False):
    """Ask for a non-empty string (unless allow_empty)."""
    while True:
        value = read_input(prompt)
        if value or allow_empty:
            return value
        print("  ! The value cannot be empty.")


def ask_yes_no(prompt):
    """
    Ask a yes/no question: True only on an explicit yes.

    Anything else is a no, and what a no means is up to the caller: it can
    ask again, as the date does, or give up, as the fulfillment does.
    """
    return read_input(prompt).strip().lower() in ("y", "yes")


def ask_int(prompt):
    """Ask for a quantity: a whole number of 1 or more, typos rejected."""
    while True:
        raw = read_input(prompt)
        try:
            value = int(raw)
        except ValueError:
            print("  ! '%s' is not a whole number. Example: 10" % raw)
            continue
        if value < 1:
            print("  ! The value must be at least 1.")
            continue
        return value


def ask_product_code(catalog, prompt="  Product (code or name | ? help+catalog "
                                     "| Enter to stop): "):
    """
    Ask the operator to pick a product without needing to know the codes.

    The answer can be a code, a piece of the name or category; here "?"
    prints the whole catalog after the context help. When the search
    returns several products they are listed and picked by their position.
    """
    show_catalog = lambda: print_product_list(catalog, "Catalog:")
    while True:
        query = read_input(prompt, show_catalog)
        if not query:
            return None

        matches = search_products(catalog, query)
        if not matches:
            print("  ! No product matches '%s'. Type ? to see the catalog." % query)
            continue
        if len(matches) == 1:
            return matches[0]["code"]

        print_product_list(matches, "%d matches:" % len(matches))
        choice = read_input("  Choose a number (empty to search again): ", show_catalog)
        if not choice:
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(matches):
            print("  ! '%s' is not one of the numbers above." % choice)
            continue
        return matches[int(choice) - 1]["code"]


def ask_priority():
    """
    Ask the fulfillment priority as a number, to avoid typing mistakes.

    The value is stored as 'normal' or 'high', which is what the order list
    and the reports display.
    """
    while True:
        answer = read_input("  Priority (0 = normal, 1 = high): ")
        if answer == "0":
            return PRIORITY_NORMAL
        if answer == "1":
            return PRIORITY_HIGH
        print("  ! Type 0 for a normal order or 1 for an urgent one.")


def today():
    """Return today's date, in the format the program writes everywhere."""
    return datetime.now().strftime(DATE_FORMAT)


def ask_date(prompt, default):
    """
    Ask for a date in YYYY-MM-DD format, today or earlier.

    Enter does not accept the default silently: today's date is proposed
    and used only after an explicit confirmation. A date ahead of today is
    refused, not flagged: it can only be a typing mistake.
    """
    while True:
        raw = read_input("%s [Enter for today, or an earlier date]: " % prompt)
        if not raw:
            if ask_yes_no("  Use today's date, %s? [y/n]: " % default):
                print("  -> date set to %s" % default)
                return default
            print("  Type the date you want, format YYYY-MM-DD.")
            continue
        try:
            datetime.strptime(raw, DATE_FORMAT)
        except ValueError:
            print("  ! Invalid date. Expected format: YYYY-MM-DD (e.g. %s)" % default)
            continue
        # Dates in this format compare as strings exactly as they do in time.
        if raw > today():
            print("  ! %s is in the future: type today's date or an earlier one."
                  % raw)
            continue
        return raw


# --------------------------------------------------------------------------
# UI ACTIONS
# --------------------------------------------------------------------------

def action_new_order(catalog, orders, operator):
    """Register a new order and show its availability status."""
    customer = ask_text("  Customer: ")
    date = ask_date("  Order date", today())
    priority = ask_priority()

    lines = []
    # Quantity asked so far per product, so that a product entered on two
    # lines is warned about on its total, the same way availability_of
    # judges the order as a whole.
    requested = {}
    print("\n  Add the order lines (leave the product empty to finish).")
    # The catalog is shown once, so that a new operator sees what can be
    # ordered; from the second line on it is available on demand with "?".
    print_product_list(catalog, "Catalog:")
    while True:
        code = ask_product_code(catalog)
        if code is None:
            break
        product = find_product(catalog, code)
        print("  -> %s %s - available: %d %s"
              % (product["code"], product["name"], product["stock"], product["unit"]))
        qty = ask_int("  Quantity: ")
        requested[code] = requested.get(code, 0) + qty
        if requested[code] > product["stock"]:
            print("  ! Only %d %s in stock: %d will stay pending."
                  % (product["stock"], product["unit"],
                     requested[code] - product["stock"]))
        lines.append({"code": code, "qty": qty, "shipped": 0})

    if not lines:
        print("  ! Order canceled: no product entered.\n")
        return

    order = {"id": next_order_id(orders), "date": date, "customer": customer,
             "priority": priority, "status": STATUS_NEW,
             "registered_by": operator,
             "fulfilled_date": None, "fulfilled_by": None,
             "lines": lines}
    orders.append(order)
    availability = availability_of(catalog, lines)
    log_operation(OP_ORDER_NEW, order["id"],
                  "customer=%s, availability=%s" % (customer, availability), operator)
    save_state(catalog, orders)
    print("\n  Order %s registered. Availability: %s\n" % (order["id"], availability.upper()))


def action_fulfill(catalog, orders, operator):
    """Fulfill an order picked from the open ones, listed in shipping order."""
    open_orders = fulfillment_sequence([o for o in orders
                                        if o["status"] != STATUS_FULFILLED])
    if not open_orders:
        print("  All orders are already fulfilled.\n")
        return

    # The open orders are printed in the sequence they should be shipped in
    # and numbered, so the operator can answer with a position instead of
    # typing the full order id.
    print("\n  Orders waiting to be fulfilled, in shipping order:")
    for index, pending in enumerate(open_orders, start=1):
        lines = format_order_lines(pending)
        print("   %-3d %-10s %-22.22s %-8s %-8s %s" %
              (index, pending["id"], pending["customer"],
               pending["priority"], pending["status"], lines))

    # A number is a position in the list above, a word is an order id: the
    # two mistakes are different and deserve different messages.
    answer = ask_text("  Order to fulfill (number or id): ")
    if answer.isdigit():
        choice = int(answer)
        if not 1 <= choice <= len(open_orders):
            print("  ! There is no number %s: the list above has %d order(s).\n"
                  % (answer, len(open_orders)))
            return
        order = open_orders[choice - 1]
    else:
        order = find_order(orders, answer)
        if not order:
            match = closest_match(answer.upper(), [o["id"] for o in orders], 0.5)
            hint = " Did you mean %s?" % match if match else ""
            print("  ! Order '%s' not found.%s\n" % (answer, hint))
            return
    if order["status"] == STATUS_FULFILLED:
        print("  ! Order %s is already fulfilled.\n" % order["id"])
        return

    # The list is the sequence the goods should go out in, so anything but
    # the first order takes the stock away from somebody who came before:
    # a more urgent order, or one of the same priority received earlier.
    # The operator is told exactly who is being overtaken, and confirms.
    position = [o["id"] for o in open_orders].index(order["id"])
    if position > 0:
        overtaken = open_orders[:position]
        print("  ! %s is number %d in the shipping order: it would overtake %s"
              % (order["id"], position + 1,
                 ", ".join("%s (%s, %s)" % (o["id"], o["priority"], o["date"])
                           for o in overtaken)))
        if not ask_yes_no("  Ship it anyway? [y/n]: "):
            print("  Order %s left as it is.\n" % order["id"])
            return

    shipped = fulfill_order(catalog, order, operator)
    save_state(catalog, orders)
    print("\n  %d unit(s) shipped. Order %s is now '%s'." % (shipped, order["id"], order["status"]))
    for line in order["lines"]:
        if line["shipped"] < line["qty"]:
            print("    pending: %s missing %d" % (line["code"], line["qty"] - line["shipped"]))
    for product in catalog:
        if needs_reorder(product):
            print("    ALERT: %s (%s) at %d %s, reorder point %d"
                  % (product["code"], product["name"], product["stock"],
                     product["unit"], product["reorder_point"]))
    print()


def action_warehouse(catalog, argument):
    """
    Show the warehouse straight away.

    "warehouse" alone prints everything, "warehouse cavi" filters by code,
    name or category, and "warehouse low" lists only the products that
    reached their reorder point.
    """
    argument = argument.strip()
    if not argument:
        print_warehouse(catalog)
        return
    if argument.lower() in ("low", "reorder"):
        print_warehouse(catalog, below_reorder=True)
        return
    matches = search_products(catalog, argument)
    if not matches:
        print("  ! No product matches '%s'.\n" % argument)
        return
    print_warehouse(matches)


def action_adjust_stock(catalog, orders, operator):
    """Manually adjust the stock of a product (restock or correction)."""
    code = ask_product_code(catalog)
    if code is None:
        return
    product = find_product(catalog, code)
    lot = product["lot_size"]
    unit = product["unit"]
    print("  %s %s" % (product["code"], product["name"]))
    print("  Current stock: %d %s" % (product["stock"], unit))
    print("  Lot size     : %d %s per lot (stock moves in whole lots only)"
          % (lot, unit))

    # The operator reasons in lots, not in single units: the quantity is
    # therefore always a multiple of the purchase lot.
    while True:
        raw = ask_text("  Number of lots (e.g. 2 to load, -1 to remove): ")
        try:
            lots = int(raw)
        except ValueError:
            print("  ! '%s' is not a whole number of lots." % raw)
            continue
        if lots == 0:
            print("  ! Zero lots means no change; type 'h' to go back.")
            continue
        break

    delta = lots * lot
    print("  -> %+d lot(s) of %d %s = %+d %s" % (lots, lot, unit, delta, unit))
    if product["stock"] + delta < 0:
        print("  ! Only %d %s in stock: you cannot remove %d %s.\n"
              % (product["stock"], unit, -delta, unit))
        return

    change_stock(catalog, code, delta, operator, MOVEMENT_MANUAL,
                 "adjustment, %+d lot(s) of %d" % (lots, lot))
    save_state(catalog, orders)
    print("  New stock of %s: %d %s\n" % (code, product["stock"], unit))


def action_report(catalog, orders):
    """Build, print and export the daily report."""
    day = ask_date("  Report date", today())
    text = build_daily_report(catalog, orders, day)
    print("\n" + text + "\n")
    path = export_report(text, day)
    print("  Report exported to %s\n" % path)


# --------------------------------------------------------------------------
# MAIN LOOP
# --------------------------------------------------------------------------

MENU_ALIASES = {
    "1": "order", "order": "order",
    "2": "fulfill", "fulfill": "fulfill",
    "3": "warehouse", "warehouse": "warehouse",
    "4": "stock", "stock": "stock",
    "5": "orders", "orders": "orders",
    "6": "report", "report": "report",
    "?": "help", "help": "help",
    "h": "menu", "menu": "menu", "back": "menu",
    "q": "quit", "quit": "quit", "exit": "quit",
}


def main():
    print(BANNER)
    catalog = load_json(CATALOG_FILE, SEED_CATALOG)
    orders = load_json(ORDERS_FILE, SEED_ORDERS)
    init_log()
    print("Data loaded: %d products, %d orders." % (len(catalog), len(orders)))

    # Every log row is signed with this name, as required by the traceability
    # requirement; pressing Enter accepts the default operator.
    operator = ask_text("Operator name [Enter for %s]: " % DEFAULT_OPERATOR,
                        allow_empty=True) or DEFAULT_OPERATOR
    print("Operator: %s - every operation will be logged under this name.\n"
          % operator)
    log_operation(OP_SESSION_START, "-", "operator logged in", operator)
    print(HELP_TEXT)

    while True:
        set_context("menu")
        entry = input("LogiServe [menu: 1 order 2 fulfill 3 warehouse 4 stock "
                      "5 orders 6 report | ? help | q quit]\n> ").strip()
        if not entry:
            continue
        # A command may carry an argument, e.g. "warehouse cavi".
        parts = entry.split(None, 1)
        choice = parts[0].lower()
        argument = parts[1] if len(parts) > 1 else ""

        command = MENU_ALIASES.get(choice)
        if command is None:
            # Typo check on the command itself.
            match = closest_match(choice, list(MENU_ALIASES), 0.6)
            hint = " Did you mean '%s'?" % match if match else ""
            print("  ! Unknown command '%s'.%s Type ? for the command list." % (choice, hint))
            continue

        # Only "warehouse" reads what follows the command: swallowing the
        # rest without a word would leave the operator waiting for an
        # effect that never comes.
        if argument and command != "warehouse":
            print("  ! '%s' ignored: only 'warehouse' takes a text after the command."
                  % argument)

        if command == "quit":
            break
        if command == "menu":
            # Already here: just show the prompt again.
            continue

        # Header of the action: it separates the commands on screen and
        # tells the operator where they are and how to get out.
        print("\n" + SEPARATOR)
        print("  %s" % ACTION_TITLES[command])
        print("  %s" % KEYS_HINT)
        print(SEPARATOR)
        set_context(command)

        # Inside an action the operator can type 'h' to come back here or
        # 'q' to leave: both arrive as exceptions handled below.
        try:
            if command == "order":
                action_new_order(catalog, orders, operator)
            elif command == "fulfill":
                action_fulfill(catalog, orders, operator)
            elif command == "warehouse":
                action_warehouse(catalog, argument)
            elif command == "stock":
                action_adjust_stock(catalog, orders, operator)
            elif command == "orders":
                print_orders(orders)
            elif command == "report":
                action_report(catalog, orders)
            elif command == "help":
                print(HELP_TEXT)
        except BackToMenu:
            print("  Operation canceled, back to the menu.\n")
        except QuitProgram:
            break

    save_state(catalog, orders)
    log_operation(OP_SESSION_END, "-", "state saved", operator)
    print("State saved in '%s'. Goodbye!" % DATA_DIR)


if __name__ == "__main__":
    try:
        main()
    except (QuitProgram, BackToMenu):
        # Only reachable before the menu starts (operator name prompt).
        print("Goodbye!")
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Data saved after the last completed operation.")


"""
NOTE DI PROGETTO - scelte, semplificazioni e sviluppi futuri
============================================================

Questa sezione documenta le decisioni prese in fase di sviluppo e i limiti
consapevoli dell'applicativo, per distinguere ciò che è una scelta di
progetto da ciò che sarebbe un difetto.

Scelte di semplificazione o aggiuntive
-------------------------

1. Nome dell'operatore a testo libero.
   All'avvio l'operatore digita il proprio nome, o accetta con Invio quello
   proposto per default ("Operatore Test"). Non esiste un elenco di utenti
   abilitati né una procedura di autenticazione: il nome serve unicamente
   a firmare le operazioni. La scelta è esemplificativa e mantiene
   l'esercizio concentrato sulla logica di magazzino.

2. Operatore conservato anche nei dati, non solo nello storico.
   Ogni ordine porta con sé chi lo ha registrato ("registered_by") e chi
   lo ha evaso ("fulfilled_by"), così che file degli ordini e file di log
   siano l'uno lo specchio dell'altro. Tre i limiti noti. Con evasioni
   parziali ripetute l'ordine conserva solo l'ultimo operatore che ha
   spedito, mentre il log ne conserva la sequenza. Per la stessa ragione
   conserva solo l'ultima data di evasione ("fulfilled_date"), riscritta
   ad ogni spedizione: il report di una giornata passata può quindi
   cambiare a posteriori, perché conta come evasi i soli ordini la cui
   ultima spedizione cade in quel giorno. Il catalogo prodotti, infine,
   non ha un campo operatore, per cui l'autore dei carichi e delle
   rettifiche di magazzino resta registrato nel solo file di log.

3. Cliente dell'ordine a testo libero.
   Per la stessa ragione dell'operatore il cliente viene digitato per
   esteso e non scelto da un'anagrafica: non esiste una lista clienti da
   cui attingere, quindi ogni ordine porta con sé il nome del proprio
   committente. Il limite noto è che due grafie diverse dello stesso
   cliente ("Officina Rossi" e "officina rossi") risultino a sistema come
   due clienti distinti.

4. Carico del magazzino per lotti d'acquisto.
   Il carico e la rettifica delle giacenze non avvengono per singole unità
   ma per lotti interi (bobine da 100 m di cavo, scatole da 4 plafoniere),
   secondo il campo "lot_size" definito per ogni prodotto. E' una scelta
   voluta, per avvicinare il comportamento a quello di un magazzino reale,
   dove la merce arriva nel confezionamento del fornitore e non sfusa.

5. Dati di esempio inventati.
   Catalogo prodotti, ordini e storico operazioni presenti alla prima
   esecuzione sono dati simulati, creati per rendere il programma
   immediatamente provabile: i codici, i nomi dei componenti elettrici,
   i clienti e le quantità non corrispondono ad alcun listino reale.

6. Storico operazioni coerente con i dati di esempio.
   Il file di log creato alla prima esecuzione non contiene righe di
   riempimento: riproduce esattamente i movimenti dei due ordini di
   esempio, perché quantità vendute e variazioni di giacenza dei report
   sono ricostruite leggendo il log e non gli ordini. Senza quelle righe
   il report del 30/07 mostrerebbe un ordine evaso senza merce uscita dal
   magazzino. Il limite noto è che i tre file vengono seminati in modo
   indipendente: cancellandone uno solo (ad esempio i soli ordini, per
   ripartire da zero con le registrazioni) si ottiene uno stato
   incoerente, perché catalogo e storico restano quelli già in uso. Per
   tornare davvero ai dati di esempio va cancellata l'intera cartella
   "data/".

7. Tasti globali solo dove il programma pone una domanda.
   I tre tasti ?, h e q valgono al menu e ad ogni singola domanda, ed è
   là che servono. Le due voci di sola lettura, magazzino ed elenco
   ordini, non chiedono nulla: stampano e tornano al menu, quindi non
   offrono un punto in cui premerli. Il promemoria resta comunque nella
   loro intestazione, e il testo previsto per esse in CONTEXT_HELP è di
   conseguenza documentazione a codice, non una schermata raggiungibile.

8. Tolleranza ai refusi nella digitazione.
   Il programma usa la libreria standard difflib per proporre il più
   simile in tre punti: sul codice prodotto, sull'identificativo
   dell'ordine da evadere e sul comando di menu. E' sempre un
   suggerimento e mai una sostituzione automatica, così che la
   correzione resti all'operatore. La soglia sui comandi (0.6) è più
   severa di quella sui codici (0.5): un comando sbagliato si ribatte in
   un istante, un codice no.

9. Scorte negative impedite anziché gestite.
   La traccia parla di "gestione di scorte negative o ordini parziali":
   qui la giacenza non scende mai sotto zero. L'evasione spedisce al
   massimo quello che c'è e lascia il resto in attesa sulla riga
   d'ordine; la rettifica manuale rifiuta un prelievo che sfonderebbe
   lo zero. Una giacenza negativa sarebbe un numero che non corrisponde
   a nulla di presente in magazzino, mentre il residuo da consegnare è
   già scritto sulle righe degli ordini, che è il posto in cui serve.

10. Nomi dei campi diversi da quelli della traccia.
    I file di dati usano nomi inglesi, come il resto del codice, mentre
    la traccia elenca le colonne in italiano. La corrispondenza:

      CodiceProdotto   -> code            IDOrdine       -> id
      Nome             -> name            Data           -> date
      Categoria        -> category        Cliente        -> customer
      GiacenzaIniziale -> stock           Stato          -> status
      PuntoRiordino    -> reorder_point   ElencoProdotti -> lines
      UnitaMisura      -> unit

    Due differenze non sono solo di nome. "stock" è la giacenza
    corrente, non quella iniziale: cambia ad ogni evasione e ad ogni
    carico. E "lot_size" è un campo in più rispetto alla traccia,
    richiesto dal carico per lotti descritto al punto 4.

11. Disponibilita' misurata sulla giacenza, non sugli impegni.
    Alla registrazione lo stato "disponibile / parziale / indisponibile"
    confronta le quantità chieste con la merce presente in quel momento,
    senza sottrarre quella già promessa agli ordini aperti. 


Sviluppi futuri
---------------

1. Inserimento di nuovi prodotti a magazzino, oggi possibile solo
   modificando a mano il file del catalogo.

2. Anagrafica clienti: selezione del committente da un elenco esistente
   e inserimento di nuovi clienti, con codice identificativo proprio.

3. Gestione degli operatori: scelta dell'operatore con cui accedere e
   assegnazione di permessi differenziati, in modo che a ciascun ruolo
   siano consentiti solo alcuni comandi (ad esempio la sola consultazione
   del magazzino per il personale di banco, l'evasione e la rettifica
   delle giacenze per il responsabile).

4. Reportistica automatica: all'avvio il programma legge lo storico
   operazioni e genera da solo il report della giornata precedente, senza
   che l'operatore debba richiederlo giorno per giorno.

5. Annullamento e correzione di un ordine già registrato, oggi possibile
   solo modificando a mano il file degli ordini. Andra' scritto nello
   storico con operatore e motivo, come ogni altra operazione: un ordine
   che sparisce senza lasciare traccia varrebbe meno del problema risolto.
"""
