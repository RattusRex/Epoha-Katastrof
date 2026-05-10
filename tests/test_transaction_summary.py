import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Amn_man import (
    FoundItemView,
    SelfFoundItemView,
    SelfSoldItemView,
    SoldItemView,
    send_transaction_summary,
)


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, message):
        self.messages.append(message)


class FakeChannel:
    def __init__(self, name):
        self.name = name
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


class FakeGuild:
    def __init__(self, channels):
        self.text_channels = channels


class FakeInteraction:
    def __init__(self, guild):
        self.guild = guild
        self.response = FakeResponse()


def test_send_transaction_summary_posts_same_message_to_response_and_log_channel():
    log_channel = FakeChannel("Учёт-транзакций")
    other_channel = FakeChannel("другой-канал")
    interaction = FakeInteraction(FakeGuild([other_channel, log_channel]))

    asyncio.run(send_transaction_summary(interaction, "# Покупка\n1) Меч +1"))

    assert interaction.response.messages == ["# Покупка\n1) Меч +1"]
    assert log_channel.messages == ["# Покупка\n1) Меч +1"]
    assert other_channel.messages == []


def test_send_transaction_summary_does_not_fail_without_log_channel():
    interaction = FakeInteraction(FakeGuild([FakeChannel("общий")]))

    asyncio.run(send_transaction_summary(interaction, "# Продажа\n1) Щит"))

    assert interaction.response.messages == ["# Продажа\n1) Щит"]


@pytest.mark.parametrize(
    "view",
    [
        FoundItemView("Обычный", "Меч +1", 2.5, 100, "Мидей", "нет"),
        SoldItemView("Обычный", "Меч +1", 2.5, 100, "Мидей", "нет"),
        SelfFoundItemView("Обычный", "Меч +1", 3, 100, "Мидей", "нет"),
        SelfSoldItemView("Обычный", "Меч +1", 3, 100, "Мидей", "нет"),
    ],
)
def test_all_final_transaction_buttons_post_once_to_log_channel(view):
    log_channel = FakeChannel("Учёт-транзакций")
    interaction = FakeInteraction(FakeGuild([log_channel]))

    button = view.children[0]
    asyncio.run(button.callback(interaction))

    assert interaction.response.messages == [view.get_summary()]
    assert log_channel.messages == [view.get_summary()]
