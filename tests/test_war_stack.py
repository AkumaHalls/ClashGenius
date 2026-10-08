"""Testes da LANE 4a: war_predictor com atacante None e post_war_analysis com stars None."""
from types import SimpleNamespace

import pytest

from cogs.post_war_analysis import (
    _format_attack_line,
    _format_bad_attack_line,
    analyze_war,
    create_post_war_analysis_embed,
)
from war_predictor import AdvancedFeatureEngineer, AdvancedWarFeatures


def _attack(stars, order, attacker_tag="#OUR", defender_tag="#B1", destruction=50):
    attacker = None if attacker_tag is None else SimpleNamespace(clan=SimpleNamespace(tag=attacker_tag))
    return SimpleNamespace(
        attacker=attacker,
        order=order,
        stars=stars,
        destruction=destruction,
        defender_tag=defender_tag,
    )


def _war_with_broken_attack():
    war = SimpleNamespace(
        team_size=2,
        attacks_per_member=2,
        attacks=[
            _attack(3, 1, attacker_tag="#OUR", defender_tag="#B1"),
            _attack(0, 2, attacker_tag=None, defender_tag="#B2"),
            _attack(2, 3, attacker_tag="#OPP", defender_tag="#B1"),
        ],
    )
    our_clan = SimpleNamespace(
        tag="#OUR",
        stars=5,
        destruction=55.5,
        attacks_used=2,
        members=[SimpleNamespace(town_hall=15, attacks=[_attack(3, 1)])],
    )
    opponent = SimpleNamespace(
        tag="#OPP",
        stars=3,
        destruction=40.0,
        attacks_used=1,
        members=[SimpleNamespace(town_hall=15, attacks=[])],
    )
    return war, our_clan, opponent


def test_temporal_features_nao_quebram_com_atacante_none():
    war, our_clan, opponent = _war_with_broken_attack()
    engineer = AdvancedFeatureEngineer()

    features = engineer._extract_temporal_features(war, our_clan, opponent)

    assert "momentum_indicator" in features


def test_coordination_features_nao_quebram_com_atacante_none():
    war, our_clan, _opponent = _war_with_broken_attack()
    engineer = AdvancedFeatureEngineer()

    features = engineer._extract_coordination_features(war, our_clan)

    assert "clan_synergy_score" in features


async def test_extract_all_features_retorna_features_com_atacante_none():
    war, our_clan, opponent = _war_with_broken_attack()
    engineer = AdvancedFeatureEngineer()

    features = await engineer.extract_all_features(war, our_clan, opponent, "#OUR")

    assert isinstance(features, AdvancedWarFeatures)
    assert features.momentum_indicator == pytest.approx(0.6)
    assert features.star_difference == pytest.approx(2.0)


def test_format_attack_line_tolerar_stars_none():
    line = _format_attack_line(
        {
            "stars": None,
            "defender_townhall": 15,
            "attacker_townhall": 14,
            "attacker_name": "Alfa",
            "defender_name": "Bravo",
            "destruction": 42,
        },
        index=1,
    )

    assert "Alfa" in line
    assert "42%" in line


def test_format_bad_attack_line_tolerar_stars_none():
    line = _format_bad_attack_line(
        {
            "stars": None,
            "defender_townhall": 15,
            "attacker_townhall": 14,
            "attacker_name": "Alfa",
            "defender_name": "Bravo",
            "destruction": 0,
        },
        index=1,
    )

    assert "nenhuma estrela" in line


def _war_doc_stars_none():
    return {
        "_id": "guerra-stars-none",
        "war_data": {
            "team_size": 2,
            "attacks_per_member": 2,
            "clan_stars": 5,
            "opponent_stars": 3,
            "clan_destruction": 55.5,
            "opponent_destruction": 40.0,
            "opponent_name": "Los Galacticos",
        },
        "our_clan_members_in_war": [
            {"tag": "#TAGA", "name": "Alfa", "townhall": 15, "attacks_made": []},
        ],
        "opponent_clan_members_in_war": [],
        "all_attacks": [
            {
                "stars": None,
                "destruction": 42,
                "defender_townhall": 15,
                "attacker_townhall": 14,
                "attacker_tag": "#TAGA",
                "defender_tag": "#B1",
                "attacker_name": "Alfa",
                "defender_name": "Bravo",
                "order": 1,
            },
        ],
    }


def test_analyze_war_tolerar_stars_none():
    stats = analyze_war(_war_doc_stars_none())

    assert stats["star_efficiency"] > 0
    assert stats["best_players"][0]["total_stars"] == 0
    assert stats["zero_star_attacks"][0]["stars"] == 0


def test_embed_pos_guerra_nao_retorna_none_com_stars_none():
    embeds = create_post_war_analysis_embed(_war_doc_stars_none())

    assert embeds
    assert embeds[0].title
