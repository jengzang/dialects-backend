from app.service.user.leaderboard_service import CATEGORY_RULES, _build_leaderboard_sql


def test_notes_endpoint_belongs_to_character_tone_category():
    assert "/api/notes" in CATEGORY_RULES["category_字調查詢"]["paths"]


def test_notes_endpoint_has_an_individual_leaderboard_dimension():
    _, key_order, _ = _build_leaderboard_sql()

    assert "endpoint__api_notes" in key_order
