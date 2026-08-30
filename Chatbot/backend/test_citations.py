"""Test del filtro sulle citazioni. Offline: non chiama il modello.

Il RAG restituisce fino a tre articoli, ma il modello ne usa nel testo solo
quelli che gli servono. Mostrare fra le fonti anche gli altri rompe il patto su
cui si regge l'interfaccia — ogni targhetta corrisponde a un'affermazione — e
una targhetta che non rimanda a niente insegna a non fidarsi neanche delle altre.
"""
import main


def test_recognises_citation_forms():
    text = "Il platano va potato ogni 36 mesi (Art. 10)."
    assert main._article_cited("Art. 10", text)
    assert main._article_cited("Art. 10", "Vedi Art.10 del regolamento.")
    assert main._article_cited("Art. 5", "definita dall art 5 del regolamento")


def test_does_not_confuse_articles_sharing_a_prefix():
    # senza confine di parola, "Art. 5" risulterebbe citato da "Art. 50"
    assert not main._article_cited("Art. 5", "Vedi Art. 50 per altro.")
    assert not main._article_cited("Art. 1", "Vedi Art. 15 per i tutelati.")


def test_unmentioned_article_is_not_cited():
    text = "Entro 400 metri sono presenti 3 alberi in classe C."
    for reference in ("Art. 4", "Art. 5", "Art. 14"):
        assert not main._article_cited(reference, text)


def test_sources_drop_unused_articles():
    results = [
        (
            "consult_regulation",
            {
                "articles": [
                    {"reference": "Art. 10", "title": "Potatura", "text": "...",
                     "source": "regolamento_verde.md", "relevance": 1.0},
                    {"reference": "Art. 14", "title": "Abbattimento", "text": "...",
                     "source": "regolamento_verde.md", "relevance": 0.4},
                ]
            },
        )
    ]
    text = "Il platano si pota ogni 36 mesi (Art. 10)."
    _, articles, _ = main._collect_references(results, text)
    assert [a["reference"] for a in articles] == ["Art. 10"]


def test_trees_stay_even_when_not_mentioned():
    """Gli alberi seguono una regola diversa: anche quelli non citati nel testo
    sono evidenziati sulla mappa, quindi la targhetta rimanda a qualcosa."""
    tree = {
        "id": "ALB-0001", "common_name": "Tiglio", "species": "Tilia cordata",
        "district": "Gries-San Quirino", "risk_class": "A",
        "months_since_inspection": 4, "lat": 46.5, "lng": 11.33,
    }
    trees, _, _ = main._collect_references(
        [("search_trees", {"trees": [tree]})], "Nessun codice qui."
    )
    assert [t["id"] for t in trees] == ["ALB-0001"]


def test_chart_keeps_filters_out_of_the_title():
    results = [
        (
            "cadastre_stats",
            {
                "group_by": "risk_class",
                "filters": "classe C/D · entro 400 m da Scuola Primaria Gries",
                "total": 3,
                "counts": [{"key": "C", "count": 3}],
            },
        )
    ]
    _, _, chart = main._collect_references(results, "")
    assert chart["title"] == "Alberi per classe di rischio"
    assert "entro 400 m" in chart["subtitle"]


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
