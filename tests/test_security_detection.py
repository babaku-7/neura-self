import asyncio
import math
import unittest
from datetime import timedelta
from types import SimpleNamespace

import discord

from cogs.security import Security


MONITOR_ID = 408785106942164992
CHANNEL_ID = 1525049168236904508


class _Bot:
    def __init__(self):
        self.config = {
            "core": {"monitor_bot_id": str(MONITOR_ID)},
            "security": {
                "enabled": True,
                "notifications": {"enabled": False},
                "webhook": {"enabled": False},
                "captcha_solver": {"enabled": False},
                "open_captcha_url_on_pc": False,
            },
        }
        self.is_mobile = False
        self.owo_user = None
        self.user = SimpleNamespace(id=705180660419133490)
        self.username = "bttrfly"
        self.channels = [str(CHANNEL_ID)]
        self.channel_id = CHANNEL_ID
        self.paused = False
        self.manual_paused = False
        self.throttle_until: float = 0.0
        self.stats = {}
        self.logs = []
        self._solving_captcha = False
        self.security_pause_reason: str | None = None
        self.captcha_detected = False
        self.web_solver = SimpleNamespace(
            mark_verification_done=lambda bot_id: None,
        )
        self.captcha_solver = _CaptchaSolver()

    def is_message_for_me(self, message):
        return False

    def log(self, log_type, message):
        self.logs.append((log_type, message))

    def get_cog(self, name):
        return None


class _CaptchaSolver:
    async def solve_image(self, image_url, letter_count):
        return "abcde"


class _TypingContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Channel:
    def __init__(self):
        self.sent = []

    async def send(self, content):
        self.sent.append(content)

    def typing(self):
        return _TypingContext()


class _Attachment:
    url = "https://cdn.example/captcha.png"


class _Message:
    def __init__(self, content="", embeds=None, dm=False, attachments=None):
        self.author = SimpleNamespace(id=MONITOR_ID)
        self.guild = None if dm else SimpleNamespace()
        self.channel = _Channel() if dm else SimpleNamespace(id=CHANNEL_ID)
        self.created_at = discord.utils.utcnow()
        self.content = content
        self.embeds = embeds or []
        self.attachments = attachments or []
        self.components = []


class _Embed:
    title = None
    description = None
    author = None
    footer = None
    url = None

    def __init__(self, fields):
        self.fields = fields


class SecurityDetectionTests(unittest.TestCase):
    def _security_for(self, bot):
        security = Security(bot)
        security.play_beep = _noop_async
        return security

    def test_captcha_pauses_even_when_identity_match_fails(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(
            security.on_message(
                _Message("Please complete this captcha to continue")
            )
        )

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))
        self.assertTrue(any(kind == "ALARM" for kind, _ in bot.logs))

    def test_captcha_in_embed_field_pauses_without_message_content(self):
        bot = _Bot()
        security = self._security_for(bot)
        embed = _Embed(
            [SimpleNamespace(name="Verification", value="Verify that you are human")]
        )

        asyncio.run(security.on_message(_Message(embeds=[embed])))

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_ban_signal_sets_infinite_throttle(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(security.on_message(_Message("You have been banned for botting")))

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_letterword_dm_pauses_before_solver_finishes(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(
            security.on_message(
                _Message(
                    "Please DM me the following 5 letterword",
                    dm=True,
                    attachments=[_Attachment()],
                )
            )
        )

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_verify_that_you_are_a_human_is_detected(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(security.on_message(_Message("Verify that you are a human!")))

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_real_human_variant_is_detected(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(security.on_message(_Message("Verify that you are a real human!")))

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_bare_captcha_url_is_detected(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(security.on_message(_Message("https://owobot.com/captcha")))

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_verification_does_not_clear_ban_pause(self):
        bot = _Bot()
        bot.paused = True
        bot.throttle_until = float("inf")
        bot.security_pause_reason = "ban"
        security = self._security_for(bot)

        asyncio.run(
            security.on_message(
                _Message("I have verified that you are human", dm=True)
            )
        )

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_forbidden_pause_cannot_be_downgraded_to_captcha(self):
        bot = _Bot()
        bot.paused = True
        bot.throttle_until = float("inf")
        bot.security_pause_reason = "forbidden"
        security = self._security_for(bot)

        asyncio.run(security.on_message(_Message("Please complete this captcha")))

        self.assertEqual(bot.security_pause_reason, "forbidden")
        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_stale_verification_does_not_resume_captcha_pause(self):
        bot = _Bot()
        bot.paused = True
        bot.throttle_until = float("inf")
        bot.security_pause_reason = "captcha"
        message = _Message("I have verified that you are human", dm=True)
        message.created_at -= timedelta(seconds=120)
        security = self._security_for(bot)

        asyncio.run(security.on_message(message))

        self.assertTrue(bot.paused)
        self.assertTrue(math.isinf(bot.throttle_until))

    def test_manual_pause_survives_captcha_verification(self):
        bot = _Bot()
        bot.paused = True
        bot.manual_paused = True
        bot.throttle_until = float("inf")
        bot.security_pause_reason = "captcha"
        security = self._security_for(bot)

        asyncio.run(
            security.on_message(
                _Message("I have verified that you are human", dm=True)
            )
        )

        self.assertTrue(bot.paused)
        self.assertIsNone(bot.security_pause_reason)

    def test_unrelated_human_text_does_not_pause(self):
        bot = _Bot()
        security = self._security_for(bot)

        asyncio.run(security.on_message(_Message("A human player joined the game")))

        self.assertFalse(bot.paused)
        self.assertEqual(bot.throttle_until, 0)


async def _noop_async():
    return None


if __name__ == "__main__":
    unittest.main()
