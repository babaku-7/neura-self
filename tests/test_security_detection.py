import asyncio
import math
import unittest
from types import SimpleNamespace

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
        self.throttle_until = 0
        self.stats = {}
        self.logs = []
        self._solving_captcha = False
        self.web_solver = SimpleNamespace()

    def is_message_for_me(self, message):
        return False

    def log(self, log_type, message):
        self.logs.append((log_type, message))


class _Message:
    def __init__(self, content="", embeds=None):
        self.author = SimpleNamespace(id=MONITOR_ID)
        self.guild = SimpleNamespace()
        self.channel = SimpleNamespace(id=CHANNEL_ID)
        self.content = content
        self.embeds = embeds or []
        self.attachments = []
        self.components = []


class _Embed:
    title = None
    description = None
    author = None
    footer = None

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


async def _noop_async():
    return None


if __name__ == "__main__":
    unittest.main()
