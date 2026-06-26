import asyncio
import json
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable

AIRA_HOME = Path.home() / ".aira"
GATEWAY_CONFIG = AIRA_HOME / "gateway.json"

_gateways: dict = {}
_message_handler: Callable | None = None


def _load_config() -> dict:
    if GATEWAY_CONFIG.exists():
        try:
            return json.loads(GATEWAY_CONFIG.read_text())
        except Exception:
            pass
    return {"telegram": {}, "discord": {}, "slack": {}, "signal": {}}


def _save_config(cfg: dict):
    AIRA_HOME.mkdir(exist_ok=True)
    GATEWAY_CONFIG.write_text(json.dumps(cfg, indent=2))


def set_message_handler(handler: Callable):
    global _message_handler
    _message_handler = handler


def gateway_status() -> list[dict]:
    return [
        {"platform": p, "running": bool(g.get("running")), "error": g.get("error", "")}
        for p, g in _gateways.items()
    ]


# ── Telegram ──
def _run_telegram(token: str):
    try:
        import asyncio
        from telegram import Update
        from telegram.ext import Application, MessageHandler, filters

        async def handle(update: Update, ctx):
            text = update.message.text if update.message else ""
            user = f"telegram:{update.effective_user.id}" if update.effective_user else "unknown"
            if text and _message_handler:
                resp = _message_handler(text, user, "telegram")
                if resp:
                    await update.message.reply_text(resp[:4000])

        app = Application.builder().token(token).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
        app.run_polling()
    except Exception as e:
        _gateways.get("telegram", {})["error"] = str(e)
        raise


# ── Discord ──
def _run_discord(token: str):
    try:
        import discord
        intents = discord.Intents.default()
        intents.message_content = True

        class Bot(discord.Client):
            async def on_message(self, msg):
                if msg.author == self.user:
                    return
                text = msg.content
                user = f"discord:{msg.author.id}"
                if text and _message_handler:
                    resp = _message_handler(text, user, "discord")
                    if resp:
                        await msg.channel.send(resp[:2000])

        bot = Bot(intents=intents)
        bot.run(token)
    except Exception as e:
        _gateways.get("discord", {})["error"] = str(e)
        raise


# ── Slack ──
def _run_slack(token: str, signing_secret: str = ""):
    try:
        from slack_sdk.rtm import RTMClient

        @RTMClient.run_on(event="message")
        def handle(**payload):
            data = payload.get("data", {})
            text = data.get("text", "")
            user = f"slack:{data.get('user', 'unknown')}"
            if text and _message_handler and not text.startswith("<@"):
                resp = _message_handler(text, user, "slack")
                if resp:
                    _gateways["slack"]["client"].web_client.chat_postMessage(
                        channel=data["channel"], text=resp[:4000]
                    )

        client = RTMClient(token=token)
        _gateways.setdefault("slack", {})["client"] = client
        client.start()
    except Exception as e:
        _gateways.get("slack", {})["error"] = str(e)
        raise


# ── Signal (via signal-cli) ──
def _run_signal(phone: str):
    try:
        import subprocess
        import time
        while True:
            r = subprocess.run(
                ["signal-cli", "-u", phone, "receive"],
                capture_output=True, text=True, timeout=30
            )
            for line in r.stdout.split("\n"):
                if "Body:" in line:
                    text = line.split("Body:", 1)[1].strip()
                    user = f"signal:{phone}"
                    if text and _message_handler:
                        resp = _message_handler(text, user, "signal")
                        if resp:
                            subprocess.run(
                                ["signal-cli", "-u", phone, "send", "-m", resp[:4000]],
                                capture_output=True, timeout=10
                            )
            time.sleep(5)
    except Exception as e:
        _gateways.get("signal", {})["error"] = str(e)
        raise


def gateway_connect(platform: str) -> dict:
    cfg = _load_config()
    pcfg = cfg.get(platform, {})
    if not pcfg:
        return {"success": False, "error": f"No config for {platform}. Set token/key first."}

    def worker():
        try:
            if platform == "telegram":
                _run_telegram(pcfg.get("token", ""))
            elif platform == "discord":
                _run_discord(pcfg.get("token", ""))
            elif platform == "slack":
                _run_slack(pcfg.get("token", ""), pcfg.get("signing_secret", ""))
            elif platform == "signal":
                _run_signal(pcfg.get("phone", ""))
        except Exception as e:
            err = str(e)
            if platform in _gateways:
                _gateways[platform]["error"] = err

    t = threading.Thread(target=worker, daemon=True, name=f"gateway-{platform}")
    t.start()
    _gateways[platform] = {"running": True, "error": "", "thread": t}
    return {"success": True, "platform": platform}


def gateway_disconnect(platform: str) -> dict:
    if platform in _gateways:
        _gateways[platform]["running"] = False
        del _gateways[platform]
        return {"success": True, "platform": platform}
    return {"success": False, "error": f"Gateway '{platform}' not running"}


def gateway_set_config(platform: str, key: str, value: str) -> dict:
    cfg = _load_config()
    if platform not in cfg:
        return {"success": False, "error": f"Unknown platform: {platform}"}
    cfg[platform][key] = value
    _save_config(cfg)
    return {"success": True, "platform": platform, "key": key}


def gateway_validate_token(platform: str) -> dict:
    """Test if the stored credentials actually work."""
    cfg = _load_config().get(platform, {})
    try:
        if platform == "telegram":
            token = cfg.get("token", "")
            if not token:
                return {"valid": False, "error": "No token set"}
            import urllib.request, json
            r = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
            data = json.loads(r.read())
            if data.get("ok"):
                bot_name = data["result"].get("first_name", "")
                return {"valid": True, "info": f"@{data['result'].get('username', '')} ({bot_name})"}
            return {"valid": False, "error": data.get("description", "Invalid token")}

        elif platform == "discord":
            token = cfg.get("token", "")
            if not token:
                return {"valid": False, "error": "No token set"}
            import urllib.request, json
            req = urllib.request.Request(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {token}"}
            )
            r = urllib.request.urlopen(req, timeout=10)
            data = json.loads(r.read())
            return {"valid": True, "info": f"@{data.get('username', '')}#{data.get('discriminator', '0')}"}

        elif platform == "slack":
            token = cfg.get("token", "")
            if not token:
                return {"valid": False, "error": "No token set"}
            import urllib.request, json
            req = urllib.request.Request(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"}
            )
            r = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if r.get("ok"):
                return {"valid": True, "info": r.get("team", "") + " / " + r.get("user", "")}
            return {"valid": False, "error": r.get("error", "Invalid token")}

        elif platform == "signal":
            phone = cfg.get("phone", "")
            if not phone:
                return {"valid": False, "error": "No phone number set"}
            import subprocess
            r = subprocess.run(["signal-cli", "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return {"valid": False, "error": "signal-cli not installed"}
            return {"valid": True, "info": f"signal-cli ready ({phone})"}

    except urllib.error.HTTPError as e:
        return {"valid": False, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"valid": False, "error": f"Network: {e.reason}"}
    except ImportError:
        return {"valid": False, "error": "Missing urllib (should be built-in)"}
    except Exception as e:
        return {"valid": False, "error": str(e)[:60]}


def gateway_get_config() -> dict:
    cfg = _load_config()
    safe = {}
    for p, c in cfg.items():
        safe[p] = {k: "***set***" if v else "" for k, v in c.items()}
    return safe
