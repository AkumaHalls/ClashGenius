"""FIX-02: validação de env vars do config (fail-fast + env vazia)."""
import importlib
import os

import pytest


@pytest.fixture
def config_with_env():
    """Recarrega `config` com env alterada; restaura o ambiente ao final."""
    import config

    salvo = dict(os.environ)

    def _apply(**env):
        for nome, valor in env.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor
        return importlib.reload(config)

    yield _apply
    os.environ.clear()
    os.environ.update(salvo)
    importlib.reload(config)


def test_channel_id_vazio_usa_default(config_with_env):
    cfg = config_with_env(CHANNEL_ID="")
    assert cfg.CHANNEL_ID == 0


def test_channel_id_valido_continua_funcionando(config_with_env):
    cfg = config_with_env(CHANNEL_ID="123456")
    assert cfg.CHANNEL_ID == 123456


def test_var_obrigatoria_ausente_gera_runtimeerror_listando_nomes(config_with_env):
    with pytest.raises(RuntimeError) as excinfo:
        config_with_env(DISCORD_TOKEN=None, COC_EMAIL=None)
    mensagem = str(excinfo.value)
    assert "DISCORD_TOKEN" in mensagem
    assert "COC_EMAIL" in mensagem


def test_fernet_key_invalida_gera_runtimeerror_claro(config_with_env):
    with pytest.raises(RuntimeError) as excinfo:
        config_with_env(FERNET_KEY="isto-nao-e-uma-chave-fernet")
    assert "FERNET_KEY" in str(excinfo.value)
