"""Telegram bot notification service."""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = bool(bot_token and chat_id)

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a text message to the configured chat."""
        if not self.enabled:
            logger.warning("Telegram not configured, skipping notification")
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    },
                )
                data = resp.json()
                if data.get("ok"):
                    logger.info(f"Telegram message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {data}")
                    return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def format_event_alert(self, event: dict) -> str:
        """Format an event into a Telegram alert message."""
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        category_emoji = {
            "gangguan_telekomunikasi": "📡",
            "gangguan_bts": "🗼",
            "gangguan_fiber": "🔗",
            "gangguan_microwave": "📶",
            "gangguan_internet": "🌐",
            "gangguan_listrik": "⚡",
            "bencana": "🌊",
            "cuaca_ekstrem": "🌪️",
            "lainnya": "📌",
        }

        sev = severity_emoji.get(event.get("severity", "medium"), "⚪")
        cat = category_emoji.get(event.get("category", "lainnya"), "📌")

        location = event.get("kabupaten", "Lampung")
        if event.get("kecamatan"):
            location += f", {event['kecamatan']}"

        lines = [
            f"{sev} <b>INSIDEN TERDETEKSI</b> {sev}",
            "",
            f"{cat} <b>{event.get('title', 'Tanpa judul')}</b>",
            "",
            f"📍 <b>Lokasi:</b> {location}",
            f"📊 <b>Severity:</b> {event.get('severity', '-').upper()}",
            f"📁 <b>Kategori:</b> {event.get('category', '-').replace('_', ' ').title()}",
            f"📰 <b>Sumber:</b> {event.get('source', '-')}",
        ]

        if event.get("description"):
            desc = event["description"][:200]
            lines.append(f"\n📝 {desc}...")

        if event.get("source_url"):
            lines.append(f"\n🔗 <a href=\"{event['source_url']}\">Baca selengkapnya</a>")

        if event.get("occurred_at"):
            lines.append(f"\n⏰ {event['occurred_at']}")

        return "\n".join(lines)

    def format_daily_summary(self, events: list[dict], date_str: str) -> str:
        """Format a daily summary of events."""
        if not events:
            return f"📊 <b>Summary Harian {date_str}</b>\n\n✅ Tidak ada insiden terdeteksi hari ini."

        # Count by category
        categories = {}
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        kabupatens = {}

        for e in events:
            cat = e.get("category", "lainnya")
            categories[cat] = categories.get(cat, 0) + 1
            sev = e.get("severity", "low")
            severities[sev] = severities.get(sev, 0) + 1
            kab = e.get("kabupaten", "Unknown")
            kabupatens[kab] = kabupatens.get(kab, 0) + 1

        lines = [
            f"📊 <b>Summary Harian {date_str}</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📈 Total insiden: <b>{len(events)}</b>",
            "",
            "🔴 Severity:",
            f"  Critical: {severities.get('critical', 0)}",
            f"  High: {severities.get('high', 0)}",
            f"  Medium: {severities.get('medium', 0)}",
            f"  Low: {severities.get('low', 0)}",
            "",
            "📁 Kategori:",
        ]

        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat.replace('_', ' ').title()}: {count}")

        if kabupatens:
            lines.append("")
            lines.append("📍 Lokasi terdampak:")
            for kab, count in sorted(kabupatens.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"  {kab}: {count}")

        return "\n".join(lines)

    async def send_event_alert(self, event: dict) -> bool:
        """Send an event alert to Telegram."""
        message = self.format_event_alert(event)
        return await self.send_message(message)

    async def send_daily_summary(self, events: list[dict], date_str: str) -> bool:
        """Send daily summary to Telegram."""
        message = self.format_daily_summary(events, date_str)
        return await self.send_message(message)


def create_notifier(bot_token: str = "", chat_id: str = "") -> TelegramNotifier:
    """Create a TelegramNotifier instance."""
    from backend.core.config import get_settings
    settings = get_settings()
    return TelegramNotifier(
        bot_token=bot_token or settings.TELEGRAM_BOT_TOKEN,
        chat_id=chat_id or settings.TELEGRAM_CHAT_ID,
    )
