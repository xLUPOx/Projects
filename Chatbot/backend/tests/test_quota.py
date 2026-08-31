"""Test della classificazione dei 429 e del pool di chiavi. Offline.

Il limite al minuto si supera aspettando, quello giornaliero no. Sbagliare la
distinzione costa caro in due modi: si ritenta a vuoto per minuti, e poi il
report della suite eval accusa il prompt di un problema che sta nella quota.
Gemini manda un `retryDelay` in *entrambi* i casi, quindi il campo da guardare
e' il `quotaId`.
"""
import sys
import time
from pathlib import Path

# I test stanno in backend/tests/, i moduli in backend/: senza questo
# `import cadastre` non risolve. Stesso accorgimento di eval/run.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import keys
import main

# Non toglie le chiavi dall ambiente come test_api/test_agent: qui non si
# passa mai da startup(), quindi ne cadastre ne rag vengono inizializzati e
# nessun client Gemini viene costruito. Se un giorno un test di questo file
# chiamasse startup(), la chiave andrebbe tolta come fanno gli altri.
PER_MINUTE = (
    "429 RESOURCE_EXHAUSTED ... 'quotaId': "
    "'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', "
    "'quotaValue': '5' ... 'retryDelay': '31s'"
)

PER_DAY = (
    "429 RESOURCE_EXHAUSTED ... 'quotaId': "
    "'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
    "'quotaValue': '20' ... 'retryDelay': '59s'"
)

# Payload completo come lo serializza l'SDK, non una versione accorciata: e' la
# forma reale che la regex deve reggere, comprese le parentesi e gli a capo.
FULL_PAYLOAD = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
    "'You exceeded your current quota, please check your plan and billing details.', "
    "'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': "
    "'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': "
    "'generativelanguage.googleapis.com/generate_content_free_tier_requests', "
    "'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', "
    "'quotaDimensions': {'model': 'gemini-3.6-flash', 'location': 'global'}, "
    "'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', "
    "'retryDelay': '17s'}]}}"
)


def _error(message: str) -> Exception:
    return type("FakeError", (Exception,), {})(message)


def test_per_minute_limit_is_worth_waiting_for():
    assert main._suggested_wait(_error(PER_MINUTE)) == 32.0


def test_per_day_limit_is_not_retried():
    # anche se il payload promette 59s: aspettare non sblocca nulla
    assert main._suggested_wait(_error(PER_DAY)) is None


def test_error_without_details_is_not_retried():
    assert main._suggested_wait(_error("errore generico")) is None


def test_full_sdk_payload():
    assert main._suggested_wait(_error(FULL_PAYLOAD)) == 18.0


def test_quota_message_is_actionable():
    for word in ("fatturazione", "chiave", "oggi"):
        assert word in main.QUOTA_EXHAUSTED.lower()


def test_daily_and_minute_limits_are_told_apart():
    """La stessa distinzione di _suggested_wait, ma dal lato di chi decide se
    mettere la chiave in pausa o metterla da parte."""
    assert main._is_daily_quota(_error(PER_DAY))
    assert not main._is_daily_quota(_error(PER_MINUTE))


def test_the_pool_reads_a_comma_separated_list():
    assert keys.load("a, b ,c") == ["a", "b", "c"]
    # una chiave ripetuta darebbe l'illusione di un margine che non c'e':
    # la quota e' la stessa
    assert keys.load("a,a,b") == ["a", "b"]
    assert keys.load("") == []


def test_a_key_at_the_minute_limit_is_paused_not_burned():
    """Il limite al minuto passa da solo: la chiave va messa in pausa, non
    buttata via, altrimenti dopo tre domande la demo resta senza chiavi."""
    keys.load("a,b")
    keys.mark_paused("a", 30)
    assert keys.usable() == "b"

    keys.mark_paused("b", 10)
    assert keys.usable() is None
    wait = keys.wait_time()
    assert wait is not None and 0 < wait <= 10  # si aspetta la prima che torna


def test_a_paused_key_comes_back_on_its_own():
    keys.load("a")
    keys.mark_paused("a", 5)
    assert keys.usable() is None
    assert keys.usable(now=time.monotonic() + 6) == "a"


def test_a_key_exhausted_for_the_day_leaves_the_pool():
    """E qui aspettare non serve: `wait_time` deve dire None, altrimenti lo
    stream dorme per niente prima di arrendersi."""
    keys.load("a,b")
    keys.mark_exhausted("a")
    assert keys.usable() == "b"

    keys.mark_exhausted("b")
    assert keys.usable() is None
    assert keys.wait_time() is None


def test_an_exhausted_key_is_tried_again_later():
    """Le quote di Google si azzerano a mezzanotte del fuso Pacifico. Tenendo
    la chiave fuori fino al riavvio, un backend acceso da prima di quell'ora
    resta senza chiavi mentre Google le ha gia' riabilitate."""
    keys.load("a")
    keys.mark_exhausted("a")
    assert keys.usable() is None

    dopo = time.monotonic() + keys.EXHAUSTED_RETRY_S + 1
    assert keys.usable(now=dopo) == "a"
    # ma nel frattempo non si aspetta: si risonda alla domanda dopo
    assert keys.wait_time() is None


def test_an_exhausted_key_does_not_promise_a_wait():
    """Caso misto: una esaurita per oggi, una in pausa. L'attesa e' quella
    della sola chiave che tornera' buona."""
    keys.load("a,b")
    keys.mark_exhausted("a")
    keys.mark_paused("a", 3_600)  # ininfluente: quella chiave e' fuori
    keys.mark_paused("b", 20)
    wait = keys.wait_time()
    assert wait is not None and wait <= 20


def test_status_says_why_a_demo_stopped():
    keys.load("a,b,c")
    keys.mark_exhausted("a")
    keys.mark_paused("b", 30)
    assert keys.status() == {"total": 3, "usable": 1, "exhausted": 1}
    keys.load("")  # stato pulito per gli altri file


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
