"""Test del retriever. Girano in modalita' BM25 (nessuna API key richiesta)."""
import os

os.environ.pop("GEMINI_API_KEY", None)  # forza il retriever lessicale

import rag  # noqa: E402


def test_chunking_per_article():
    rag.initialize()
    references = [c["reference"] for c in rag._chunks]
    assert "Art. 10" in references
    assert "Art. 15" in references
    assert len(references) == len(set(references)), "riferimenti duplicati"


def test_retrieves_pruning_article():
    r = rag.search("ogni quanto va potato un platano?")
    assert r["found"] > 0
    assert "Art. 10" in [a["reference"] for a in r["articles"]]


def test_retrieves_inspection_article():
    r = rag.search("con che frequenza vanno ispezionati gli alberi in classe D?")
    assert "Art. 5" in [a["reference"] for a in r["articles"]]


def test_retrieves_felling_article():
    r = rag.search("quando si puo' abbattere un albero?")
    assert "Art. 14" in [a["reference"] for a in r["articles"]]


def test_out_of_domain_question_returns_nothing():
    # e' il caso che permette all'agente di dire "il regolamento non lo prevede"
    # invece di citare l'articolo meno peggio
    for question in [
        "quali sono gli orari della biblioteca comunale?",
        "chi ha vinto il campionato di calcio?",
    ]:
        r = rag.search(question)
        assert r["found"] == 0, f"{question} -> {r['articles']}"
        assert r["notice"]


def test_every_result_is_citable():
    r = rag.search("distanze da rispettare in cantiere")
    for a in r["articles"]:
        assert a["reference"]
        assert a["source"] == "regolamento_verde.md"
        assert 0.0 <= a["relevance"] <= 1.0


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
    print(f"modalita: {rag.mode()}")
    print("tutti i test passati" if not failed else f"{failed} test falliti")
