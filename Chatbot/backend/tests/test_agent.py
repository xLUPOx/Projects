"""Test del ciclo dell'agente. Offline: il modello e' finto, la rete non serve.

E' la parte piu' importante del backend e finora la vedeva solo `eval/run.py`,
che pero' chiama Gemini davvero: serve una chiave, consuma quota e non e'
deterministico. Cosi' il turno, il dispatch della `function_call`, il rientro di
un errore nel contesto e il tetto sui giri non erano coperti da niente che si
potesse lanciare a costo zero.

Il finto client sostituisce solo l'ultimo miglio — `generate_content_stream` —
con chunk costruiti con i tipi veri dell'SDK. Tutto il resto (i tool, il
catasto, il RAG, il filtro sulle citazioni) e' quello di produzione.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any

from google.genai import errors, types

# I test stanno in backend/tests/, i moduli in backend/: senza questo
# `import cadastre` non risolve. Stesso accorgimento di eval/run.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # importa per primo: e' lui a caricare .env

# Senza chiave il RAG indicizza con BM25 invece che con gli embedding, quindi
# nemmeno l'avvio tocca la rete. Va fatto dopo l'import di main (che legge .env)
# e prima di inizializzare il RAG, perche' initialize() e' idempotente e la
# modalita' si decide li' una volta sola.
# keys.py legge prima GEMINI_API_KEYS: vanno tolte entrambe, altrimenti
# con un pool in .env questo test "offline" chiamerebbe la rete.
for _var in ("GEMINI_API_KEYS", "GEMINI_API_KEY"):
    os.environ.pop(_var, None)

import cadastre  # noqa: E402
import rag  # noqa: E402
import keys  # noqa: E402
from test_cadastre import DEMO_FACTS  # noqa: E402  - i numeri stanno scritti li'

cadastre.initialize()
rag.initialize()


def _chunk(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


def _text(value: str) -> types.Part:
    return types.Part(text=value)


def _call(name: str, **args: Any) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


class FakeModels:
    def __init__(self, turns: list[list[types.GenerateContentResponse]]):
        self.turns = turns
        self.calls: list[dict[str, Any]] = []

    def generate_content_stream(self, *, model, contents, config):
        # Il contesto che il ciclo ha accumulato fin qui: e' quello che il
        # modello vedrebbe davvero, e i test ci asseriscono sopra.
        self.calls.append({"contents": list(contents), "config": config})
        index = min(len(self.calls) - 1, len(self.turns) - 1)
        return iter(self.turns[index])


class FakeClient:
    def __init__(self, turns):
        self.models = FakeModels(turns)


def _run(turns, question="domanda") -> tuple[list[dict[str, Any]], FakeClient]:
    """Esegue lo stream con il finto client e restituisce gli eventi decodificati."""
    client = FakeClient(turns)
    previous = main._client
    main._client = client
    try:
        events = [
            json.loads(line.removeprefix("data: ").strip())
            for line in main._stream_agent(main.ChatRequest(question=question))
        ]
    finally:
        main._client = previous
    return events, client


def _types(events) -> list[str]:
    return [e["type"] for e in events]


def test_plain_answer_without_tools():
    events, _ = _run([[_chunk(_text("Non "), _text("posso rispondere."))]])
    assert _types(events) == ["text", "text", "end"]
    assert "".join(e["delta"] for e in events if e["type"] == "text") == "Non posso rispondere."
    end = events[-1]
    assert end["trees"] == [] and end["articles"] == [] and end["chart"] is None
    assert end["tools_used"] == []


def test_tool_call_is_executed_and_announced_before_the_result():
    """L'ordine degli eventi e' l'interfaccia: `status` esce *prima* che il tool
    giri, altrimenti la chat non mostra niente mentre l'attesa e' in corso."""
    events, client = _run([
        [_chunk(_call("search_trees", district="Gries", species="tiglio"))],
        [_chunk(_text("Sei tigli a Gries: ALB-0001."))],
    ])

    assert _types(events) == ["status", "tool", "text", "end"]

    status, tool = events[0], events[1]
    assert status["name"] == "search_trees"
    assert status["args"] == {"district": "Gries", "species": "tiglio"}
    assert status["text"] == "Interrogo il catasto alberi"
    tigli = DEMO_FACTS["tigli_a_gries"]
    assert tool["result"] == f"{tigli} alberi corrispondenti"  # il tool ha girato davvero

    assert events[-1]["tools_used"] == ["search_trees"]
    assert len(events[-1]["trees"]) == tigli

    # e l'esito e' rientrato nel contesto per il giro dopo
    assert len(client.models.calls) == 2
    last_part = client.models.calls[1]["contents"][-1].parts[0]
    assert last_part.function_response.name == "search_trees"


def test_bad_arguments_come_back_as_a_correctable_error():
    """Un argomento fuori schema non deve rompere lo stream: torna al modello
    come risultato del tool, che nella maggior parte dei casi si corregge."""
    events, client = _run([
        [_chunk(_call("search_trees", quartiere="Gries"))],  # nome inventato
        [_chunk(_text("Riprovo."))],
    ])

    assert _types(events) == ["status", "tool", "text", "end"]
    assert "Argomenti non validi" in events[1]["result"]
    response = client.models.calls[1]["contents"][-1].parts[0].function_response
    assert "Argomenti non validi" in response.response["error"]


def test_unknown_tool_does_not_crash_the_stream():
    events, _ = _run([
        [_chunk(_call("cerca_alberi"))],  # tool che non esiste
        [_chunk(_text("Uso quelli disponibili."))],
    ])
    assert _types(events) == ["status", "tool", "text", "end"]
    assert "Tool sconosciuto" in events[1]["result"]


def test_turn_limit_stops_the_loop():
    """Senza tetto, un modello che continua a chiamare tool gira all'infinito.
    Il limite deve fermarlo *e* chiudere comunque con un evento `end`."""
    events, client = _run([[_chunk(_call("allowed_values"))]])  # sempre lo stesso giro

    assert _types(events).count("status") == main.MAX_AGENT_TURNS
    assert _types(events)[-1] == "end"
    assert len(client.models.calls) == main.MAX_AGENT_TURNS


def test_only_the_articles_actually_cited_reach_the_sources():
    """Lo stesso patto verificato in test_citations.py, ma attraverso il ciclo
    intero: il RAG ne restituisce fino a tre, in "Fonti" va solo cio' che il
    testo nomina."""
    events, _ = _run([
        [_chunk(_call("consult_regulation", question="ogni quanto va potato un platano?"))],
        [_chunk(_text("Il platano va potato ogni 36 mesi (Art. 10)."))],
    ])
    end = events[-1]
    assert [a["reference"] for a in end["articles"]] == ["Art. 10"]


def test_stats_produce_the_chart():
    events, _ = _run([
        [_chunk(_call("cadastre_stats", group_by="risk_class"))],
        [_chunk(_text("La maggior parte e' in classe A."))],
    ])
    chart = events[-1]["chart"]
    assert chart["title"] == "Alberi per classe di rischio"
    assert sum(item["count"] for item in chart["items"]) == 140


def test_parallel_calls_in_one_turn():
    """Il modello puo' chiedere due tool nello stesso giro: devono girare
    entrambi, in ordine, e tornare entrambi nel contesto."""
    events, client = _run([
        [_chunk(
            _call("search_trees", district="Gries", species="tiglio"),
            _call("consult_regulation", question="potatura del platano"),
        )],
        [_chunk(_text("Fatto (Art. 10), vedi ALB-0001."))],
    ])
    assert _types(events) == ["status", "tool", "status", "tool", "text", "end"]
    assert events[-1]["tools_used"] == ["search_trees", "consult_regulation"]
    assert len(client.models.calls[1]["contents"][-1].parts) == 2


def test_generation_is_pinned_to_zero_temperature():
    """La suite eval giudica per sottostringa: con il campionamento acceso
    misurerebbe la varianza del modello invece dell'agente."""
    _, client = _run([[_chunk(_text("ok"))]])
    assert client.models.calls[0]["config"].temperature == 0
    assert client.models.calls[0]["config"].automatic_function_calling.disable is True


class ExhaustedModels:
    """Un client la cui chiave ha finito la quota, scelta col `quotaId`."""

    def __init__(self, quota_id: str):
        self.quota_id = quota_id
        self.calls = 0

    def generate_content_stream(self, **_):
        self.calls += 1
        raise errors.ClientError(429, {"error": {
            "message": f"quotaId: '{self.quota_id}', retryDelay: '31s'",
            "status": "RESOURCE_EXHAUSTED",
        }})


class ExhaustedClient:
    def __init__(self, quota_id: str):
        self.models = ExhaustedModels(quota_id)


def _run_with_pool(clients: dict, question="domanda"):
    """Come _run, ma con un pool di chiavi vero: la rotazione la decide `keys`."""
    keys.load(",".join(clients))
    saved = (main._clients, main._client, main._active_key)
    main._clients = clients
    main._client, main._active_key = None, None
    assert main._switch_key(), "nessuna chiave utilizzabile all'avvio"
    try:
        events = [
            json.loads(line.removeprefix("data: ").strip())
            for line in main._stream_agent(main.ChatRequest(question=question))
        ]
    finally:
        main._clients, main._client, main._active_key = saved
        keys.load("")
    return events


def test_a_key_out_of_daily_quota_hands_over_to_the_next():
    """Il limite giornaliero non passa aspettando: la chiave esce dal giro e
    la domanda la serve la successiva, nello stesso stream."""
    bruciata = ExhaustedClient("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    buona = FakeClient([[_chunk(_text("Sei tigli."))]])

    events = _run_with_pool({"k1": bruciata, "k2": buona})

    assert _types(events) == ["text", "end"]
    assert bruciata.models.calls == 1  # provata una volta sola, poi da parte
    assert buona.models.calls[0]["contents"][-1].parts[0].text == "domanda"


def test_the_minute_limit_changes_key_instead_of_sleeping():
    """Con piu' chiavi, aspettare 31 secondi e' uno spreco: la pausa serve solo
    quando sono al limite tutte quante."""
    in_pausa = ExhaustedClient("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")
    buona = FakeClient([[_chunk(_text("ok"))]])

    def vietato(_seconds):
        raise AssertionError("ha dormito invece di cambiare chiave")

    dormita = main.time.sleep
    main.time.sleep = vietato
    try:
        events = _run_with_pool({"k1": in_pausa, "k2": buona})
    finally:
        main.time.sleep = dormita

    assert _types(events) == ["text", "end"]


def test_when_every_key_is_out_the_error_says_so():
    """Nessuna chiave libera e nessuna che tornera' libera: si smette, e il
    messaggio parla di fatturazione, non di un errore generico."""
    events = _run_with_pool({
        "k1": ExhaustedClient("GenerateRequestsPerDayPerProjectPerModel-FreeTier"),
        "k2": ExhaustedClient("GenerateRequestsPerDayPerProjectPerModel-FreeTier"),
    })
    assert _types(events) == ["error"]
    assert events[0]["quota"] is True
    assert events[0]["message"] == main.QUOTA_EXHAUSTED


def test_missing_key_says_what_to_do():
    previous = main._client
    main._client = None
    try:
        events = [
            json.loads(line.removeprefix("data: ").strip())
            for line in main._stream_agent(main.ChatRequest(question="x"))
        ]
    finally:
        main._client = previous
    assert _types(events) == ["error"]
    assert ".env" in events[0]["message"]


def test_summaries_are_readable():
    """La riga sotto la chiamata al tool e' cio' che l'utente legge mentre
    aspetta: deve dire un numero, non 'ok'."""
    assert main._summarize_result("search_trees", {"total_matching": 6}) == "6 alberi corrispondenti"
    assert main._summarize_result("x", {"error": "Luogo assente"}) == "Luogo assente"
    assert main._summarize_result(
        "consult_regulation",
        {"found": 1, "articles": [{"reference": "Art. 10"}]},
    ) == "1 articoli (Art. 10)"
    assert main._summarize_result("consult_regulation", {"found": 0, "articles": []}) == "nessun articolo"
    assert main._summarize_result("cadastre_stats", {"counts": [1, 2]}) == "2 gruppi"
    assert main._summarize_result("allowed_values", {"total_trees": 140}) == "140 alberi a catasto"


def test_history_reaches_the_model_in_order():
    """Il frontend manda la conversazione precedente e le domande di seguito
    ("e quelli in classe C?") dipendono da lei. `_history_to_contents` tiene gli
    ultimi otto messaggi e ci aggiunge la domanda nuova."""
    request = main.ChatRequest(
        question="E quelli in classe C?",
        history=[main.ChatMessage(role="user" if i % 2 == 0 else "assistant", text=f"m{i}")
                 for i in range(10)],
    )
    contents = main._history_to_contents(request)
    assert len(contents) == 9  # otto di storia + la domanda
    assert [c.role for c in contents[:4]] == ["user", "model", "user", "model"]
    assert contents[0].parts[0].text == "m2"  # i due piu' vecchi sono caduti
    assert contents[-1].parts[0].text == "E quelli in classe C?"


if __name__ == "__main__":
    failed = 0
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            try:
                function()
                print(f"  ok   {name}")
            except AssertionError as e:
                failed += 1
                print(f"  FAIL {name}: {e}")
    print("tutti i test passati" if not failed else f"{failed} test falliti")
