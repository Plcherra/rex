from app.services.entity_normalization_service import EntityNormalizationService


def test_normalize_candidate_entity_resolves_obsolete_project_name():
    service = EntityNormalizationService()
    known_entities = [
        {
            "id": "entity-echodesk",
            "entity_type": "project",
            "display_name": "EchoDesk",
            "normalized_name": "echodesk",
            "aliases": [],
            "metadata": {"obsolete_aliases": ["Echotask"]},
            "active": True,
        }
    ]

    result = service.normalize_candidate_entity(
        {
            "entity_type": "project",
            "display_name": "Echotask",
            "normalized_name": "echotask",
            "aliases": ["Echotask"],
            "metadata": {},
        },
        known_entities,
    )

    assert result.changed is True
    assert result.canonical_entity["id"] == "entity-echodesk"
    assert result.payload["display_name"] == "EchoDesk"
    assert result.payload["normalized_name"] == "echodesk"
    assert result.payload["aliases"] == []
    assert result.payload["metadata"]["canonical_entity_id"] == "entity-echodesk"
    assert result.payload["metadata"]["obsolete_aliases"] == ["echotask"]


def test_normalize_candidate_entity_keeps_obsolete_person_name_out_of_aliases():
    service = EntityNormalizationService()
    known_entities = [
        {
            "id": "entity-melissa",
            "entity_type": "person",
            "display_name": "Melissa",
            "normalized_name": "melissa",
            "aliases": ["coworker"],
            "metadata": {"obsolete_names": ["Al", "AI"]},
            "active": True,
        }
    ]

    result = service.normalize_candidate_entity(
        {
            "entity_type": "person",
            "display_name": "Al",
            "normalized_name": "al",
            "aliases": ["AI", "coworker"],
            "metadata": {},
        },
        known_entities,
    )

    assert result.payload["display_name"] == "Melissa"
    assert result.payload["normalized_name"] == "melissa"
    assert result.payload["aliases"] == ["coworker"]
    assert set(result.payload["metadata"]["obsolete_aliases"]) == {"ai", "al"}


def test_normalize_payload_references_rewrites_text_and_links_entity():
    service = EntityNormalizationService()
    known_entities = [
        {
            "id": "entity-flowforce",
            "entity_type": "project",
            "display_name": "FlowForce",
            "normalized_name": "flowforce",
            "aliases": [],
            "metadata": {"obsolete_aliases": ["Flowfirst", "Flowforte"]},
            "active": True,
        }
    ]

    result = service.normalize_payload_references(
        {
            "title": "Launch Flowfirst",
            "description": "Finish Flowforte MVP.",
            "primary_entity_id": None,
            "metadata": {},
        },
        known_entities,
        text_fields=("title", "description"),
        link_field="primary_entity_id",
    )

    assert result.payload["title"] == "Launch FlowForce"
    assert result.payload["description"] == "Finish FlowForce MVP."
    assert result.payload["primary_entity_id"] == "entity-flowforce"
    assert result.payload["metadata"]["entity_normalization"][
        "canonical_entity_id"
    ] == "entity-flowforce"


def test_correction_pairs_from_text_detects_general_name_corrections():
    service = EntityNormalizationService()

    pairs = service.correction_pairs_from_text(
        "I misspoke: Flowfirst was wrong, the real name is FlowForce."
    )

    assert len(pairs) == 1
    assert pairs[0].old_key == "flowfirst"
    assert pairs[0].new_key == "flowforce"
