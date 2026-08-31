"""Suite di regressione sull'agente (la parte 'AI per i workflow interni').

Non e' un test unitario: e' il controllo che serve prima di toccare il prompt,
i tool o il modello. Ogni caso in cases.json dichiara cosa ci si aspetta, con
questi campi (tutti facoltativi tranne question ed expected_citations):

    expected_tools     tool che devono comparire fra quelli chiamati
    forbidden_tools    tool che non devono comparire
    must_contain       parole che devono esserci nella risposta
    must_not_contain   parole che non devono esserci
    must_contain_any   almeno una di queste: serve ai rifiuti, che hanno una
                       forma precisa ma molte formulazioni
    expected_citations trees | articles | chart | none: cosa l'interfaccia
                       mostrerebbe come fonte, non il payload — vedi _cited_trees
    chart_forbidden    vero se la domanda non deve produrre un grafico

Il confronto e' per parola intera, non per sottostringa: vedi _mentions.
Il ciclo dell'agente ha una copia dei suoi controlli in tests/test_agent.py, che gira
offline con un modello finto. Qui si misura solo cio' che quel test non puo'
vedere: se il *vero* modello sceglie i tool giusti e sta dentro le regole.

    cd backend
    python eval/run.py                  # tutti i casi
    python eval/run.py pruning_rule     # solo i casi il cui nome contiene...

Consuma direttamente lo stream dell'agente, quindi non serve avere il server su.
Serve GEMINI_API_KEY: e' l'unico test che chiama davvero il modello.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

CASES = Path(__file__).with_name("cases.json")
PAUSE_BETWEEN_CASES = float(os.getenv("EVAL_PAUSE_S", "45"))


def _mentions(term: str, text: str) -> bool:
    """Vero se il testo contiene il termine *come parola*.

    La sottostringa nuda diceva bugie in entrambe le direzioni: cercare "6" lo
    trovava dentro "36", "46,5" e "ALB-0006", quindi un caso poteva passare per
    il motivo sbagliato. Gli spazi diventano flessibili perche' "Art. 10" e
    "Art.10" sono lo stesso riferimento e il modello alterna le due forme; il
    confine di parola si applica solo se il termine comincia o finisce con un
    carattere di parola, cosi' cercare un simbolo come l'euro continua a valere.
    """
    pattern = r"\s*".join(re.escape(word) for word in term.lower().split())
    prefix = r"\b" if term[:1].isalnum() else ""
    suffix = r"\b" if term[-1:].isalnum() else ""
    return re.search(prefix + pattern + suffix, text.lower()) is not None


def _cited_trees(end: dict, text: str) -> list[dict]:
    """Gli alberi che l'interfaccia mostra davvero come fonte.

    `end["trees"]` e' il payload SSE grezzo: il backend ci manda dentro *tutti*
    gli alberi toccati dai tool, apposta, perche' la mappa ne ha bisogno per
    accendersi (vedi il docstring di `_collect_references` in main.py). Ma la
    targhetta in chat e l'evidenziazione sulla mappa le decide solo il
    frontend, filtrando su cosa il testo nomina davvero -- la stessa logica di
    `segment()` + `citedCodes()` in frontend/src/app/format.ts, rifatta qui in
    `_named_codes` perche' l'eval non ha accesso al bundle Angular: e' una
    regola duplicata in due linguaggi, ed e' il punto da riallineare se le
    targhette cambiano forma. Un controllo che guardasse `end["trees"]`
    direttamente misurerebbe cosa il backend ha consultato, non cosa l'utente
    vede: esattamente il layer sbagliato per verificare le citazioni.
    """
    return [tree for tree in end.get("trees", []) if tree["id"] in _named_codes(text)]


def _named_codes(text: str) -> set[str]:
    """I codici ALB-xxxx che il frontend trasformerebbe in targhetta.

    Le righe dentro un recinto ``` non contano: `segment()` le rende a
    spaziatura fissa senza interpretarle, quindi un codice li' dentro non
    diventa targhetta e non accende niente in mappa. La regola 8 del prompt
    vieta al modello i blocchi di codice proprio per questo, ma un controllo
    che li ignorasse darebbe per citato un albero che l'utente non vede
    cliccabile — cioe' sbaglierebbe verdetto esattamente nel caso in cui il
    modello ha disobbedito.
    """
    codes: set[str] = set()
    fenced = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            codes.update(re.findall(r"ALB-\d{4}", line))
    return codes


def run_case(case: dict) -> dict:
    request = main.ChatRequest(question=case["question"])
    text = ""
    tools_used: list[str] = []
    end: dict = {}
    error = None

    for line in main._stream_agent(request):
        event = json.loads(line.removeprefix("data: ").strip())
        if event["type"] == "text":
            text += event["delta"]
        elif event["type"] == "tool":
            tools_used.append(event["name"])
        elif event["type"] == "end":
            end = event
        elif event["type"] == "error":
            error = event["message"]

    # Un caso morto sulla quota non dice NIENTE sull'agente: va tenuto separato
    # dai fallimenti veri, altrimenti il report accusa il prompt di un problema
    # che sta nella fatturazione.
    skipped = bool(error) and "quota" in error.lower()

    problems = []
    if error and not skipped:
        problems.append(f"errore: {error}")

    if skipped:
        return {
            "name": case["name"],
            "passed": False,
            "skipped": True,
            "problems": [],
            "tools_used": tools_used,
            "response": text.strip(),
            "skip_reason": error,
        }

    for tool in case.get("expected_tools", []):
        if tool not in tools_used:
            problems.append(f"tool mancante: {tool} (usati: {tools_used or 'nessuno'})")

    # Il contrario di expected_tools, e non e' simmetrico: dire "questi tool
    # servono" e' un vincolo debole, perche' l'agente puo' sempre aggiungerne
    # (allowed_values prima di filtrare, per esempio, che la regola 6 gli
    # chiede). Il vincolo forte e' dire quale tool NON deve comparire: la
    # regola 7 vive tutta qui, un conteggio a risposta singola non passa da
    # cadastre_stats.
    for forbidden in case.get("forbidden_tools", []):
        if forbidden in tools_used:
            problems.append(f"tool che non doveva essere chiamato: {forbidden}")

    for expected in case.get("must_contain", []):
        if not _mentions(expected, text):
            problems.append(f"manca nella risposta: {expected!r}")

    for forbidden in case.get("must_not_contain", []):
        if _mentions(forbidden, text):
            problems.append(f"presente ma non dovrebbe: {forbidden!r}")

    # Un rifiuto ha una forma precisa ma molte formulazioni: basta che ne
    # compaia una. Cercare la sola parola "non", com'era prima, non asseriva
    # niente: sta dentro qualunque frase italiana, comprese quelle inventate.
    alternatives = case.get("must_contain_any", [])
    if alternatives and not any(_mentions(a, text) for a in alternatives):
        problems.append(f"nessuna forma di rifiuto riconosciuta fra {alternatives}")

    expected_citations = case["expected_citations"]
    cited_trees = _cited_trees(end, text)
    if expected_citations == "trees" and not cited_trees:
        problems.append("nessun albero citato nel testo (l'interfaccia non mostrerebbe targhette)")
    if expected_citations == "articles" and not end.get("articles"):
        problems.append("nessun articolo citato")
    if expected_citations == "chart":
        if not end.get("chart"):
            problems.append("nessun dato per il grafico")
        # Le barre riassumono alberi precisi, e la mappa deve poterli accendere.
        # `cadastre_stats` tornava soli conteggi: il grafico compariva e la
        # mappa restava spenta, senza che nessun caso se ne accorgesse. Qui si
        # guarda il payload grezzo apposta: il grafico accende in mappa *tutti*
        # gli alberi trovati, non solo quelli nominati nel testo (state.ts,
        # highlightFor: "il grafico vale quanto un codice citato").
        elif not end.get("trees"):
            problems.append("grafico senza gli alberi da evidenziare in mappa")
    if expected_citations == "none":
        # Dire *quali* fonti sono passate: senza, il fallimento costava una
        # riesecuzione della suite solo per scoprire quale dei tre secchi era
        # pieno. I nomi non cambiano il giudizio, lo rendono leggibile.
        leaked = [
            bucket
            for bucket, present in (
                ("trees", bool(cited_trees)),
                ("articles", bool(end.get("articles"))),
                ("chart", bool(end.get("chart"))),
            )
            if present
        ]
        if leaked:
            problems.append(
                "ha citato fonti per una domanda senza risposta nei dati: "
                + ", ".join(leaked)
            )

    # La regola 7 vale in entrambe le direzioni: il grafico deve comparire sulle
    # domande di ripartizione e NON comparire sui conteggi singoli. Senza questo
    # controllo il pannello appare a intermittenza e la demo diventa una lotteria.
    if case.get("chart_forbidden") and end.get("chart"):
        problems.append("ha prodotto un grafico per un conteggio a risposta singola")

    return {
        "name": case["name"],
        "passed": not problems,
        "skipped": False,
        "problems": problems,
        "tools_used": tools_used,
        "response": text.strip(),
        # Gli id grezzi dal payload, non solo quelli citati: un fallimento su
        # "trees" o "none" si rilegge da qui senza dover rifare la chiamata.
        "trees_in_payload": sorted(t["id"] for t in end.get("trees", [])),
        "articles_in_payload": sorted(
            a["reference"] for a in end.get("articles", [])
        ),
    }


def main_cli() -> int:
    name_filter = sys.argv[1] if len(sys.argv) > 1 else ""
    cases = [
        c for c in json.loads(CASES.read_text(encoding="utf-8"))
        if name_filter.lower() in c["name"].lower()
    ]
    if not cases:
        print(f"Nessun caso corrisponde a {name_filter!r}")
        return 1

    main.startup()
    if main._client is None:
        # Senza chiave ogni caso fallirebbe con lo stesso errore e il conteggio
        # finale direbbe '0 su 10' come se il problema stesse nell'agente.
        print("Nessuna chiave Gemini: questa suite chiama il modello davvero.")
        print("Crea backend/.env da .env.example. I test offline girano lo stesso.")
        return 2
    print(f"Modello: {main.MODEL} | temperatura: {main.TEMPERATURE} | casi: {len(cases)}\n")

    results = []
    for index, case in enumerate(cases):
        # Il free tier concede pochissime richieste al minuto e ogni caso ne
        # consuma 2-3: senza pausa la suite misura la quota, non l'agente.
        if index:
            time.sleep(PAUSE_BETWEEN_CASES)
        result = run_case(case)
        results.append(result)
        symbol = "SKIP" if result["skipped"] else "PASS" if result["passed"] else "FAIL"
        print(f"[{symbol}] {result['name']}")
        print(f"       tool: {', '.join(result['tools_used']) or '-'}")
        preview = " ".join(result["response"].split())[:160]
        print(f"       risp: {preview}")
        if result["skipped"]:
            print("       !!    saltato: quota Gemini esaurita")
        for p in result["problems"]:
            print(f"       !!    {p}")
        print()

    skipped = sum(r["skipped"] for r in results)
    passed = sum(r["passed"] for r in results)
    evaluated = len(results) - skipped

    if skipped:
        print(f"{skipped} casi saltati per quota Gemini esaurita: non dicono nulla")
        print("sull'agente. Riprova con una chiave con fatturazione attiva.\n")
    print(f"{passed}/{evaluated} casi valutati passati" if evaluated else "nessun caso valutato")

    report = Path(__file__).with_name("last_report.json")
    report.write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"Rapporto completo: {report}")
    if skipped:
        return 2  # esito indeterminato: la suite non ha potuto girare davvero
    return 0 if passed == evaluated else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
