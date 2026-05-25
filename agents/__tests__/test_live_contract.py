import pytest

from api.live_contract import parse_live_init_message


def test_parse_live_init_message_trims_and_normalizes():
    message = parse_live_init_message({
        "type": "init",
        "home_team": "  Barcelona  ",
        "away_team": " Real Madrid ",
        "sport": "soccer",
        "competition": " Champions League Final ",
    })

    assert message.home_team == "Barcelona"
    assert message.away_team == "Real Madrid"
    assert message.sport == "soccer"
    assert message.competition == "Champions League Final"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "match_event", "home_team": "A", "away_team": "B", "sport": "soccer"},
        {"type": "init", "home_team": "", "away_team": "B", "sport": "soccer"},
        {"type": "init", "home_team": "A", "away_team": "B", "sport": "darts"},
    ],
)
def test_parse_live_init_message_rejects_invalid_payloads(payload):
    with pytest.raises(ValueError):
        parse_live_init_message(payload)
