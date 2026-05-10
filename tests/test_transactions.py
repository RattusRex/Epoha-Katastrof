import asyncio
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


def load_bot_module(monkeypatch):
    if "Amn_man" in sys.modules:
        del sys.modules["Amn_man"]

    monkeypatch.setattr("discord.ext.commands.Bot.run", Mock())
    return importlib.import_module("Amn_man")


def test_self_found_view_uses_total_days_spent(monkeypatch):
    bot = load_bot_module(monkeypatch)

    view = bot.SelfFoundItemView(
        rarity="Обычный",
        item_name="Меч +1",
        total_days_spent=19,
        final_price=100,
        character_name="Мидей",
        consumable="нет",
    )

    summary = view.get_summary()

    assert "Потрачено дней: **19**" in summary


def test_self_sold_view_uses_total_days_spent(monkeypatch):
    bot = load_bot_module(monkeypatch)

    view = bot.SelfSoldItemView(
        rarity="Обычный",
        item_name="Меч +1",
        total_days_spent=19,
        final_price=100,
        character_name="Мидей",
        consumable="нет",
    )

    summary = view.get_summary()

    assert "Потрачено дней: **19**" in summary


def test_send_transaction_summary_logs_to_accounting_channel(monkeypatch):
    bot = load_bot_module(monkeypatch)
    log_channel = SimpleNamespace(name="Учёт-транзакций", send=AsyncMock())
    interaction = SimpleNamespace(
        guild=SimpleNamespace(text_channels=[log_channel]),
        response=SimpleNamespace(send_message=AsyncMock()),
    )

    asyncio.run(bot.send_transaction_summary(interaction, "summary text"))

    interaction.response.send_message.assert_awaited_once_with("summary text")
    log_channel.send.assert_awaited_once_with("summary text")
