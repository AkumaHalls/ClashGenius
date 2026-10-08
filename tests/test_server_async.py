"""FIX-04: web/server — download de assets não pode bloquear o event loop."""
import asyncio
from types import SimpleNamespace


class _FakeBot:
    def __init__(self):
        self.bot_version = "0.0-teste"
        self._setup_hook_done = asyncio.Event()
        self.maintenance_mode = False
        self.maintenance_message = "manutenção"
        self.api_client = None
        self.db = None
        self.web_api_cache = {}
        self.WEB_API_CACHE_DURATION_SECONDS = 45
        self._WEB_API_CACHE_MAXSIZE = 200
        self.war_prediction_system = None
        self.clan_tag = "#TEST"
        self.coc_client_ready = asyncio.Event()

    def get_cog(self, _nome):
        return SimpleNamespace()


class _ProcessoFake:
    returncode = 0

    async def communicate(self):
        return b"", b""


async def test_setup_web_server_nao_chama_subprocess_sincrono(monkeypatch, tmp_path):
    from web import server as web_server

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    import geniuslib.utils

    monkeypatch.setattr(geniuslib.utils, "get_assets_dir", lambda: str(assets_dir))
    monkeypatch.setenv("PORT", "0")

    chamadas = {"subprocess_run": 0}

    def subprocess_run_sincrono(*_args, **_kwargs):
        chamadas["subprocess_run"] += 1
        raise AssertionError("subprocess.run síncrono foi chamado dentro de async def")

    monkeypatch.setattr("subprocess.run", subprocess_run_sincrono)

    async def create_subprocess_exec_falso(*_args, **_kwargs):
        return _ProcessoFake()

    monkeypatch.setattr("asyncio.create_subprocess_exec", create_subprocess_exec_falso)

    bot = _FakeBot()
    bot._setup_hook_done.set()
    runner = None
    try:
        await asyncio.wait_for(web_server.setup_web_server(bot), timeout=10)
        runner = getattr(bot, "_web_runner", None)
        assert chamadas["subprocess_run"] == 0, "subprocess.run síncrono chamado pelo setup_web_server"
        assert runner is not None, "servidor web não subiu"
    finally:
        if runner is not None:
            await runner.cleanup()


async def test_download_assets_nao_bloqueia_event_loop(tmp_path):
    from web.server import download_assets_if_needed

    script = tmp_path / "lento.py"
    script.write_text("import time\ntime.sleep(0.5)\n", encoding="utf-8")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    ticks = 0

    async def tick():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    contador = asyncio.create_task(tick())
    try:
        ok = await asyncio.wait_for(
            download_assets_if_needed(str(assets_dir), str(script)), timeout=10
        )
    finally:
        contador.cancel()

    assert ok is True
    assert ticks >= 15, f"event loop ficou bloqueado durante o download (ticks={ticks})"


async def test_download_assets_timeout_aguarda_processo_apos_kill(monkeypatch, tmp_path):
    from web import server as web_server
    from web.server import download_assets_if_needed

    script = tmp_path / "pendura.py"
    script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    reg = {"kill": False, "wait": False}

    class _ProcessoPendura:
        returncode = None

        async def communicate(self):
            await asyncio.sleep(10)

        def kill(self):
            reg["kill"] = True

        async def wait(self):
            reg["wait"] = True

    async def _criar(*_args, **_kwargs):
        return _ProcessoPendura()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _criar)
    monkeypatch.setattr(web_server, "ASSET_DOWNLOAD_TIMEOUT", 0.1)

    ok = await asyncio.wait_for(
        download_assets_if_needed(str(assets_dir), str(script)), timeout=10
    )

    assert ok is False
    assert reg["kill"] is True, "processo deveria ser morto no timeout"
    assert reg["wait"] is True, "deve aguardar o processo terminar após kill (evitar zumbi)"


async def test_download_assets_falha_retorna_false_sem_explodir(tmp_path):
    from web.server import download_assets_if_needed

    script = tmp_path / "falha.py"
    script.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    ok = await asyncio.wait_for(
        download_assets_if_needed(str(assets_dir), str(script)), timeout=10
    )
    assert ok is False
