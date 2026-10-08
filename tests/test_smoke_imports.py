"""Smoke: o harness de testes importa os módulos centrais sob env fake."""
import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "config",
        "simple_cache",
        "formatting",
        "war_predictor",
        "web.middleware",
        "cogs.war_advisor_cog",
    ],
)
def test_import(module):
    importlib.import_module(module)
