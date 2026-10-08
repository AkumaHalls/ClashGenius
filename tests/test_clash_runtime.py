"""FIX-05/06/07c: runtime do clash — retry Mongo, shutdown/exit codes e redação de URI."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest
from discord.ext import commands


class _CursorVazio:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _ColecaoFake:
    async def find_one(self, *_args, **_kwargs):
        return None

    def find(self, *_args, **_kwargs):
        return _CursorVazio()


class _DBFake:
    def __init__(self):
        self.system_config = _ColecaoFake()
        self.war_history = _ColecaoFake()


def _fabrica_cliente_mongo(chamadas, falhar, mensagem_erro):
    class _Admin:
        async def command(self, *_args, **_kwargs):
            chamadas["ping"] += 1
            if falhar:
                raise RuntimeError(mensagem_erro)
            return {"ok": 1}

    class _Cliente:
        def __init__(self):
            self.admin = _Admin()
            self.db = _DBFake()

        def __getitem__(self, _nome):
            return self.db

    return lambda *_a, **_k: _Cliente()


def _parchear_setup_hook(monkeypatch, chamadas, falhar, mensagem_erro):
    import clash

    async def _start_early(bot_instance):
        bot_instance._early_web_runner = None

    async def _web_falso(_bot):
        return None

    async def _login_falso(_self):
        return None

    monkeypatch.setattr("web.server.start_early_health_check", _start_early)
    monkeypatch.setattr(clash, "setup_web_server", _web_falso)
    monkeypatch.setattr(clash.ClashGeniusBot, "coc_login_task", _login_falso)
    monkeypatch.setattr(clash.ClashGeniusBot, "load_extension", AsyncMock())
    monkeypatch.setattr(clash, "MONGO_RETRY_BASE_DELAY", 0.01)
    monkeypatch.setattr(
        "motor.motor_asyncio.AsyncIOMotorClient",
        _fabrica_cliente_mongo(chamadas, falhar, mensagem_erro),
    )
    return clash


async def _deixar_tarefas_rodarem():
    for _ in range(3):
        await asyncio.sleep(0)


@pytest.fixture
async def bot_setup():
    import clash

    bot = clash.ClashGeniusBot(command_prefix="!", intents=discord.Intents.default())
    bot.loop = asyncio.get_running_loop()
    yield bot
    tarefa = getattr(bot, "_mongo_reconnect_task", None)
    if tarefa is not None and not tarefa.done():
        tarefa.cancel()
        await asyncio.sleep(0)


async def test_setup_hook_mongo_falha_nao_define_db_ready(bot_setup, monkeypatch):
    chamadas = {"ping": 0}
    clash = _parchear_setup_hook(monkeypatch, chamadas, True, "connection refused")
    clash.log_handler.buffer.clear()

    await asyncio.wait_for(bot_setup.setup_hook(), timeout=15)
    await _deixar_tarefas_rodarem()

    assert not bot_setup.db_ready.is_set(), "db_ready não pode ser definido quando o Mongo falha"
    assert bot_setup.db is None
    assert chamadas["ping"] >= 5, f"esperava >=5 tentativas de ping, obteve {chamadas['ping']}"


async def test_setup_hook_mongo_sucesso_define_db_ready(bot_setup, monkeypatch):
    chamadas = {"ping": 0}
    _parchear_setup_hook(monkeypatch, chamadas, False, "")

    await asyncio.wait_for(bot_setup.setup_hook(), timeout=15)
    await _deixar_tarefas_rodarem()

    assert chamadas["ping"] >= 1
    assert bot_setup.db is not None
    assert bot_setup.db_ready.is_set()


async def test_falha_mongo_nao_registra_uri_com_credenciais(bot_setup, monkeypatch):
    import clash

    uri = "mongodb://admin:senha-secreta-123@localhost:27017/clashdb"
    monkeypatch.setattr(clash, "MONGO_DB_URL", uri)
    chamadas = {"ping": 0}
    _parchear_setup_hook(monkeypatch, chamadas, True, f"falha de conexão com {uri}")
    clash.log_handler.buffer.clear()

    await asyncio.wait_for(bot_setup.setup_hook(), timeout=15)
    await _deixar_tarefas_rodarem()

    registros = "\n".join(clash.log_handler.buffer)
    assert "senha-secreta-123" not in registros, "URI com credenciais vazou para o log"
    assert "***:***@" in registros


async def test_before_tasks_start_sem_db_retorna_sem_travar(caplog):
    from cogs.tasks_cog import TasksCog

    bot_falso = SimpleNamespace(
        db=None,
        db_ready=asyncio.Event(),
        coc_client_ready=asyncio.Event(),
        wait_until_ready=AsyncMock(),
    )
    bot_falso.db_ready.set()
    cog = TasksCog(bot_falso)

    await asyncio.wait_for(cog.before_tasks_start(), timeout=2)
    assert "bot.db está None" in caplog.text


def test_redact_mongo_uri_mascara_credenciais():
    from config import redact_mongo_uri

    uri = "mongodb://admin:senha-super-secreta@mongo.example.com:27017/clashgenius"
    saida = redact_mongo_uri(uri)
    assert "senha-super-secreta" not in saida
    assert "***:***@" in saida
    assert "mongo.example.com" in saida


async def test_diagnostics_nao_devolve_uri_com_credenciais():
    from cogs.admin_cog import AdminCog

    linha_envenenada = (
        "2026-10-08 - clash_genius_bot - ERROR - Falha: "
        "mongodb://admin:senha-super-secreta@mongo.example.com:27017/clashgenius"
    )
    bot_falso = SimpleNamespace(
        api_client=None,
        db=None,
        log_handler=SimpleNamespace(buffer=[linha_envenenada]),
    )
    cog = AdminCog(bot_falso)

    diagnostico = await cog.get_diagnostics()
    texto = "\n".join(str(linha) for linha in diagnostico["recent_logs"])
    assert "senha-super-secreta" not in texto, "URI com credenciais vazou na API de diagnóstico"
    assert "***:***@" in texto


async def test_main_retorna_1_em_erro_fatal(monkeypatch):
    import clash

    class _BotFatal:
        def __init__(self, *_args, **_kwargs):
            self._fechado = False

        async def start(self, _token):
            raise RuntimeError("explosão catastrófica no startup")

        def is_closed(self):
            return self._fechado

        def is_ready(self):
            return False

        async def close(self):
            self._fechado = True

    monkeypatch.setattr(clash, "ClashGeniusBot", _BotFatal)
    codigo = await asyncio.wait_for(clash.main(), timeout=10)
    assert codigo == 1


async def test_main_retorna_0_quando_start_encerra_normalmente(monkeypatch):
    import clash

    class _BotOk:
        def __init__(self, *_args, **_kwargs):
            self._fechado = False

        async def start(self, _token):
            return None

        def is_closed(self):
            return self._fechado

        def is_ready(self):
            return True

        async def close(self):
            self._fechado = True

    monkeypatch.setattr(clash, "ClashGeniusBot", _BotOk)
    codigo = await asyncio.wait_for(clash.main(), timeout=10)
    assert codigo == 0


async def test_close_cancela_tasks_de_background(monkeypatch):
    import clash

    async def _super_close(_self):
        return None

    monkeypatch.setattr(commands.Bot, "close", _super_close)

    bot = clash.ClashGeniusBot(command_prefix="!", intents=discord.Intents.default())
    bot.loop = asyncio.get_running_loop()

    evento = asyncio.Event()

    async def _eterna():
        await evento.wait()

    tarefa_coc = asyncio.create_task(_eterna())
    tarefa_web = asyncio.create_task(_eterna())
    bot._coc_login_task = tarefa_coc
    bot._web_server_task = tarefa_web
    try:
        await asyncio.wait_for(bot.close(), timeout=5)
        await asyncio.sleep(0)
        assert tarefa_coc.cancelled(), "tarefa _coc_login_task não foi cancelada no close"
        assert tarefa_web.cancelled(), "tarefa _web_server_task não foi cancelada no close"
    finally:
        for tarefa in (tarefa_coc, tarefa_web):
            if not tarefa.done():
                tarefa.cancel()


async def test_shutdown_gracioso_fecha_bot_mesmo_durante_startup():
    import clash

    class _BotNaoPronto:
        def __init__(self):
            self.fechado = False

        def is_closed(self):
            return self.fechado

        async def close(self):
            self.fechado = True

    bot = _BotNaoPronto()
    await asyncio.wait_for(clash._shutdown_gracioso(bot), timeout=2)
    assert bot.fechado, "shutdown gracioso deve fechar o bot mesmo durante o startup"


async def test_reconexao_mongo_propaga_db_aos_cogs(monkeypatch):
    """Cogs que capturaram db=None no __init__ precisam receber o db (re)conectado."""
    import clash

    chamadas = {"ping": 0}
    monkeypatch.setattr(clash, "MONGO_DB_URL", "mongodb://localhost:27017/clashdb")
    monkeypatch.setattr(
        "motor.motor_asyncio.AsyncIOMotorClient",
        _fabrica_cliente_mongo(chamadas, False, ""),
    )

    cog_um = SimpleNamespace(db=None)
    cog_dois = SimpleNamespace(db=None)
    sem_db = SimpleNamespace(sem_atributo_db=1)
    fake_self = SimpleNamespace(
        db=None,
        mongo_client=None,
        db_ready=asyncio.Event(),
        load_initial_state_from_db=AsyncMock(),
        cogs={"um": cog_um, "dois": cog_dois, "tres": sem_db},
    )

    ok = await asyncio.wait_for(
        clash.ClashGeniusBot._connect_mongo_with_retry(fake_self), timeout=10
    )

    assert ok is True
    assert fake_self.db is not None
    assert cog_um.db is fake_self.db, "cog não recebeu o db reconectado"
    assert cog_dois.db is fake_self.db
    assert not hasattr(sem_db, "db"), "cog sem atributo db não deve ser alterado"
    assert fake_self.db_ready.is_set()


async def test_before_tasks_start_cancela_loops_sem_db():
    """Sem bot.db, os loops de background devem ser cancelados (não apenas logados)."""
    from cogs.tasks_cog import TasksCog

    cancelados = []

    class _LoopFalso:
        def is_running(self):
            return True

        def cancel(self):
            cancelados.append(self)

    bot_falso = SimpleNamespace(
        db=None,
        db_ready=asyncio.Event(),
        coc_client_ready=asyncio.Event(),
        wait_until_ready=AsyncMock(),
    )
    bot_falso.db_ready.set()
    cog = TasksCog(bot_falso)

    loops = [_LoopFalso() for _ in range(5)]
    cog.check_war_end_task = loops[0]
    cog.donation_snapshot_task = loops[1]
    cog.cleanup_old_snapshots_task = loops[2]
    cog.check_api_status_task = loops[3]
    cog.reconcile_membership_task = loops[4]

    await asyncio.wait_for(cog.before_tasks_start(), timeout=2)

    assert cancelados == loops, "todos os loops dependentes de db deveriam ser cancelados"
