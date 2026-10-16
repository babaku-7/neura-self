import asyncio
import math
import sys
import unittest
from pathlib import Path

import discord

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.neura_human import NeuraHuman


class _ForbiddenResponse:
    status = 403
    reason = "Forbidden"
    headers = {}


def _forbidden_error():
    return discord.Forbidden(
        _ForbiddenResponse(),  # pyright: ignore[reportArgumentType]
        "Missing Permissions",
    )


class _TypingContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Channel:
    async def send(self, content):
        raise _forbidden_error()

    def typing(self):
        return _TypingContext()


class _Bot:
    def __init__(self, typing_enabled):
        self.config = {
            "stealth": {
                "typing_enabled": typing_enabled,
                "human_break": {"enabled": False},
                "speed_custom": {
                    "enabled": True,
                    "reaction_min": 0,
                    "reaction_max": 0,
                    "key_delay_min": 0,
                    "key_delay_max": 0,
                    "enter_delay_min": 0,
                    "enter_delay_max": 0,
                },
            }
        }
        self.is_on_break = False
        self.grind_active_time = 0
        self.last_break_check = 0
        self.paused = False
        self.throttle_until = 0
        self.logs = []

    def log(self, log_type, message):
        self.logs.append((log_type, message))

    def _pause_after_send_forbidden(self, error):
        self.paused = True
        self.throttle_until = float("inf")


class ForbiddenSendSafetyTests(unittest.TestCase):
    def test_forbidden_send_pauses_bot_without_typing(self):
        bot = _Bot(typing_enabled=False)

        result = asyncio.run(NeuraHuman.neura_send(bot, _Channel(), "owo"))

        self.assertFalse(result)
        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_forbidden_send_pauses_bot_during_typing_fallback(self):
        bot = _Bot(typing_enabled=True)

        result = asyncio.run(NeuraHuman.neura_send(bot, _Channel(), "owo"))

        self.assertFalse(result)
        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))


if __name__ == "__main__":
    unittest.main()
