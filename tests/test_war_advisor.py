"""FIX-03: war_advisor — loop infinito com adversário vazio e start_time como date."""
import datetime
import threading
from types import SimpleNamespace

import pytz

from cogs.war_advisor_cog import WarAdvisorSystem, WarPhase


def _membro(nome, town_hall=13, posicao=1, ataques=None):
    return SimpleNamespace(
        name=nome,
        town_hall=town_hall,
        map_position=posicao,
        attacks=ataques if ataques is not None else [],
        heroes=[],
        hero_equipment=[],
        best_opponent_attack=None,
    )


def _guerra(start_time, estado="inWar"):
    return SimpleNamespace(state=estado, start_time=start_time, attacks_per_member=2)


def test_adversario_sem_membros_termina_em_2s():
    sistema = WarAdvisorSystem()
    guerra = _guerra(datetime.datetime.now(pytz.utc))
    nosso_clan = SimpleNamespace(tag="#CLAN", members=[_membro("Atacante")])
    adversario = SimpleNamespace(tag="#INIMIGO", members=[])

    resultado = {}

    def executar():
        resultado["recomendacoes"] = sistema._generate_recommendations_via_matrix(
            guerra, nosso_clan, adversario, WarPhase.PHASE_1
        )

    thread = threading.Thread(target=executar, daemon=True)
    thread.start()
    thread.join(timeout=2.0)
    assert not thread.is_alive(), "loop de matriz com opponent.members vazio não terminou em 2s"
    assert resultado.get("recomendacoes") == []


def test_start_time_como_date_calcula_fase_sem_explodir():
    sistema = WarAdvisorSystem()
    agora = datetime.datetime.now(pytz.utc)
    guerra = _guerra((agora - datetime.timedelta(hours=13)).date())
    assert sistema._determine_war_phase(guerra) == WarPhase.PHASE_2


def test_start_time_como_datetime_calcula_fase():
    sistema = WarAdvisorSystem()
    agora = datetime.datetime.now(pytz.utc)
    guerra_recente = _guerra(agora - datetime.timedelta(hours=1))
    guerra_antiga = _guerra(agora - datetime.timedelta(hours=13))
    assert sistema._determine_war_phase(guerra_recente) == WarPhase.PHASE_1
    assert sistema._determine_war_phase(guerra_antiga) == WarPhase.PHASE_2


def test_start_time_como_timestamp_geniuslib_calcula_fase():
    sistema = WarAdvisorSystem()
    agora = datetime.datetime.now(pytz.utc)
    guerra_recente = _guerra(SimpleNamespace(time=agora - datetime.timedelta(hours=1)))
    guerra_antiga = _guerra(SimpleNamespace(time=agora - datetime.timedelta(hours=13)))
    assert sistema._determine_war_phase(guerra_recente) == WarPhase.PHASE_1
    assert sistema._determine_war_phase(guerra_antiga) == WarPhase.PHASE_2
