"""Acceptance tests for catalog discovery, generation tiers and personas.

Pure-function tests: no LLM calls, no network. They pin the tier contract
(Basic 4x3 / Working 8x4 / Mastery 12x5) from the public API metadata all the
way to the orchestrator's LEVEL_SPECS, and verify upload citations and the
selectable domain personas.
"""
from app.agents.pipeline import normalize_level
from app.graph.orchestrator import LEVEL_SPECS
from app.services import catalog
from app.services.domain_classifier import DomainClassifier


def test_public_tier_metadata_has_exact_sizes():
    tiers = {t["id"]: t for t in catalog.tiers_payload()}
    assert (tiers["basic"]["modules"], tiers["basic"]["lessons_per_module"]) == (4, 3)
    assert (tiers["working"]["modules"], tiers["working"]["lessons_per_module"]) == (8, 4)
    assert (tiers["mastery"]["modules"], tiers["mastery"]["lessons_per_module"]) == (12, 5)
    assert tiers["basic"]["total_lessons"] == 12
    assert tiers["working"]["total_lessons"] == 32
    assert tiers["mastery"]["total_lessons"] == 60


def test_tier_ids_resolve_to_canonical_levels_in_both_languages():
    expected = {
        "basic": ("Básico", "Foundational"),
        "working": ("Intermediário", "Intermediate"),
        "mastery": ("Avançado", "Advanced"),
    }
    for tier_id, (pt, en) in expected.items():
        assert catalog.resolve_level(tier_id, "pt-BR") == pt
        assert catalog.resolve_level(tier_id, "en-US") == en
        # main.py runs resolve_level -> normalize_level before the pipeline.
        assert normalize_level(catalog.resolve_level(tier_id, "pt-BR"), "pt-BR") in LEVEL_SPECS
        assert normalize_level(catalog.resolve_level(tier_id, "en-US"), "en-US") in {
            "Foundational", "Intermediate", "Advanced"
        }


def test_orchestrator_specs_match_tier_contract():
    for tier in catalog.TIERS:
        for level in (tier["level_pt"], tier["level_en"]):
            spec = LEVEL_SPECS.get(level) or {
                "modules": catalog.tier_for_level(level)["modules"],
                "lessons_per_module": catalog.tier_for_level(level)["lessons_per_module"],
            }
            assert spec["modules"] == tier["modules"], level
            assert spec["lessons_per_module"] == tier["lessons_per_module"], level


def test_category_classifier_and_difficulty_filter():
    assert catalog.classify_category("Python para sistemas distribuídos") == "code"
    assert catalog.classify_category("Piano do zero") == "music"
    assert catalog.classify_category("Trading e gestão de risco") == "money"
    assert catalog.classify_category("Neurociência da aprendizagem") == "mind"
    assert catalog.level_matches_difficulty("Básico", "basic")
    assert catalog.level_matches_difficulty("Advanced", "mastery")
    assert catalog.level_matches_difficulty("Intermediário", "working")
    assert not catalog.level_matches_difficulty("Básico", "mastery")
    assert {c["id"] for c in catalog.CATEGORIES} >= {
        "code", "music", "money", "business", "mind", "design",
        "language", "craft", "science",
    }


def test_personas_are_selectable_and_override_inferred_voice():
    personas = DomainClassifier.personas_payload()
    assert {p["id"] for p in personas} == {
        "auto", "practitioner", "socratic", "storyteller", "rigorist"
    }
    profile = {"persona_title": "AI inferred", "tone_of_voice": "AI inferred tone"}
    overridden = DomainClassifier.apply_persona(dict(profile), "socratic")
    assert overridden["persona_title"] != profile["persona_title"]
    assert overridden["selected_persona"] == "socratic"
    auto = DomainClassifier.apply_persona(dict(profile), "auto")
    assert auto["persona_title"] == profile["persona_title"]
    assert auto["selected_persona"] == "auto"


def test_uploaded_material_produces_chapter_citations():
    chunks = [
        {"title": "O Sistema Nervoso", "page_start": 3, "page_end": 12},
        {"title": "Sinapses", "page_start": 13, "page_end": 27},
    ]
    sources = catalog.document_citations(chunks, "Neurociência.pdf")
    citations = [s for s in sources if s.get("citation")]
    assert len(citations) == 2
    assert citations[0]["title"].startswith("Cap. 1")
    assert citations[0]["domain"] == "p. 3–12"
    assert citations[1]["chapter_index"] == 2
    assert sources[0]["domain"] == "Arquivo Local (PDF/EPUB)"


def test_catalog_api_exposes_tiers_personas_and_categories():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        tiers = client.get("/api/catalog/tiers").json()
        personas = client.get("/api/catalog/personas").json()
        categories = client.get("/api/catalog/categories").json()
    assert client is not None
    assert [t["id"] for t in tiers] == ["basic", "working", "mastery"]
    assert len(personas) >= 5
    assert len(categories) >= 9
