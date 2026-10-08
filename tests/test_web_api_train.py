# -*- coding: utf-8 -*-
"""Tests TDD para FIX-12 debounce em WebApiCog.fetch_clan_members_for_web."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.fixture
def make_web_cog(fake_db=None):
    from cogs import web_api_cog as wac

    bot = SimpleNamespace(
        db=fake_db,
        get_clan_data_with_cache=lambda *a, **k: None,
        get_cog=lambda *a, **k: None,
        clan_tag="#TESTCLAN",
        bot_version="test",
    )
    cog = wac.WebApiCog(bot)
    return cog, wac


def test_fix12_train_debounced_within_ttl(make_web_cog, monkeypatch):
    cog, wac = make_web_cog
    # setup bot state
    class Clan:
        members = []

    cog.bot.get_clan_data_with_cache = lambda tag: Clan()
    cog.bot.get_cog = lambda name: None  # no db/watchlist/analytics
    # but we need to test debounce path - simulate analytics cog
    calls = {"n": 0}

    class Analytics:
        async def process_and_train(self, tag):
            calls["n"] += 1

        async def get_player_insights(self, tags):
            return {"insights": []}

    # make get_cog return analytics when name is Player Analytics
    def get_cog(name):
        if name == "Player Analytics":
            return Analytics()
        return None

    cog.bot.get_cog = get_cog
    cog.db = None  # avoid war_history aggregate issues

    class T:
        def __init__(self, v):
            self.v = v

        def monotonic(self):
            return self.v

    t = T(1000.0)
    monkeypatch.setattr(wac, "time", SimpleNamespace(monotonic=t.monotonic))
    monkeypatch.setattr(wac, "cache", None)
    # first call
    asyncio.run(cog.fetch_clan_members_for_web())
    # second call within ttl
    t.v = 1000.0 + wac.ANALYTICS_TRAIN_TTL_SECONDS - 10
    asyncio.run(cog.fetch_clan_members_for_web())
    assert calls["n"] == 1


def test_fix12_train_runs_after_ttl(make_web_cog, monkeypatch):
    cog, wac = make_web_cog
    class Clan:
        members = []

    cog.bot.get_clan_data_with_cache = lambda tag: Clan()
    calls = {"n": 0}

    class Analytics:
        async def process_and_train(self, tag):
            calls["n"] += 1

        async def get_player_insights(self, tags):
            return {"insights": []}

    def get_cog(name):
        if name == "Player Analytics":
            return Analytics()
        return None

    cog.bot.get_cog = get_cog
    cog.db = None
    monkeypatch.setattr(wac, "cache", None)
    class T:
        def __init__(self, v):
            self.v = v

        def monotonic(self):
            return self.v

    t = T(1000.0)
    monkeypatch.setattr(wac, "time", SimpleNamespace(monotonic=t.monotonic))
    asyncio.run(cog.fetch_clan_members_for_web())
    t.v = 1000.0 + wac.ANALYTICS_TRAIN_TTL_SECONDS + 1
    asyncio.run(cog.fetch_clan_members_for_web())
    assert calls["n"] == 2
