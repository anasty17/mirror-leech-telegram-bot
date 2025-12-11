"""
Worker Status Command Module

Provides /workerstatus command for monitoring worker pool health,
upload/download statistics, and performance metrics with enterprise-grade UI.
"""

from time import time
from datetime import datetime, timezone
from pyrogram.filters import command, regex
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from .. import LOGGER
from ..core.telegram_manager import TgClient
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import get_readable_file_size, get_readable_time
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import send_message
from ..helper.telegram_helper.button_build import ButtonMaker


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Status Icons & Formatting
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STATUS_ICONS = {
    "healthy": "🟢",
    "degraded": "🟡", 
    "critical": "🔴",
    "READY": "✅",
    "BUSY": "🔄",
    "RATE_LIMITED": "⏳",
    "OFFLINE": "❌",
    "UNKNOWN": "❓",
}

HEALTH_LABELS = {
    "healthy": "Operational",
    "degraded": "Degraded",
    "critical": "Critical",
}


def _format_speed(mbps: float) -> str:
    """Format speed with appropriate precision."""
    if mbps >= 100:
        return f"{mbps:.0f}"
    elif mbps >= 10:
        return f"{mbps:.1f}"
    else:
        return f"{mbps:.2f}"


def _format_worker_card(session_id: str, data: dict) -> str:
    """Format individual worker as a professional card."""
    state = data.get("state", "UNKNOWN")
    icon = STATUS_ICONS.get(state, "❓")
    username = data.get("bot_username", session_id)
    
    uploads = data.get("uploads_completed", 0)
    downloads = data.get("downloads_completed", 0)
    speed = data.get("avg_speed_mbps", 0.0)
    bytes_up = data.get("bytes_uploaded_mb", 0)
    bytes_down = data.get("bytes_downloaded_mb", 0)
    
    # Build stats line
    stats = []
    if uploads > 0 or downloads > 0:
        stats.append(f"↑{uploads} ↓{downloads}")
    if bytes_up > 0 or bytes_down > 0:
        total_mb = bytes_up + bytes_down
        stats.append(f"{total_mb:.1f}MB")
    if speed > 0:
        stats.append(f"{_format_speed(speed)} MB/s")
    
    stats_str = " • ".join(stats) if stats else "No activity"
    
    return f"{icon} <code>{username}</code>\n    └ {stats_str}"


def _calculate_health_status(pool) -> tuple:
    """Calculate overall health status and message."""
    total = pool.total_count
    available = pool.available_count
    active = pool.active_count
    rate_limited = pool.rate_limited_count
    
    if total == 0:
        return "critical", "No Workers"
    
    working = available + active
    
    if working == total and rate_limited == 0:
        return "healthy", "All Systems Operational"
    elif working >= total * 0.5:
        return "degraded", "Partial Capacity"
    else:
        return "critical", "Service Degraded"


def _build_status_message(pool, dispatcher, health_data: dict) -> str:
    """Build the complete professional status message."""
    
    # Calculate health
    health_key, health_msg = _calculate_health_status(pool)
    health_icon = STATUS_ICONS[health_key]
    
    # Pool stats
    total_workers = pool.total_count
    available = pool.available_count
    active = pool.active_count
    rate_limited = pool.rate_limited_count
    offline = max(0, total_workers - available - active - rate_limited)
    
    # Aggregate metrics
    total_uploads = sum(w.get("uploads_completed", 0) for w in health_data.values())
    total_downloads = sum(w.get("downloads_completed", 0) for w in health_data.values())
    failed_uploads = sum(w.get("uploads_failed", 0) for w in health_data.values())
    failed_downloads = sum(w.get("downloads_failed", 0) for w in health_data.values())
    bytes_up = sum(w.get("bytes_uploaded_mb", 0) for w in health_data.values())
    bytes_down = sum(w.get("bytes_downloaded_mb", 0) for w in health_data.values())
    
    total_ops = total_uploads + total_downloads
    total_failed = failed_uploads + failed_downloads
    success_rate = ((total_ops - total_failed) / max(1, total_ops)) * 100
    
    # Current time
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    
    # Build message with professional formatting
    msg = f"""<b>━━━ Worker Pool Dashboard ━━━</b>

{health_icon} <b>Status:</b> {health_msg}

<b>📊 Pool Overview</b>
┌ Total Workers: <code>{total_workers}</code>
├ Available: <code>{available}</code>
├ Active: <code>{active}</code>
├ Rate Limited: <code>{rate_limited}</code>
└ Offline: <code>{offline}</code>

<b>📈 Performance Metrics</b>
┌ Uploads: <code>{total_uploads}</code> ({failed_uploads} failed)
├ Downloads: <code>{total_downloads}</code> ({failed_downloads} failed)
├ Success Rate: <code>{success_rate:.1f}%</code>
├ Data Uploaded: <code>{bytes_up:.2f} MB</code>
└ Data Downloaded: <code>{bytes_down:.2f} MB</code>
"""
    
    # Dispatcher section
    if dispatcher:
        pending = dispatcher.pending_count
        active_tasks = dispatcher.active_count
        strategy = dispatcher._scheduling.replace("_", " ").title()
        
        msg += f"""
<b>⚙️ Task Dispatcher</b>
┌ Pending: <code>{pending}</code>
├ Processing: <code>{active_tasks}</code>
└ Strategy: <code>{strategy}</code>
"""
    
    # Workers section
    msg += "\n<b>🤖 Workers</b>\n"
    
    for session_id, data in health_data.items():
        msg += f"\n{_format_worker_card(session_id, data)}"
    
    # Footer
    msg += f"\n\n<i>Last updated: {now}</i>"
    
    return msg


def _build_unconfigured_message() -> str:
    """Build message when worker pool is not configured."""
    return """<b>━━━ Worker Pool Dashboard ━━━</b>

🔴 <b>Status:</b> Not Configured

<b>ℹ️ Setup Required</b>

Worker pool is not enabled. To enable parallel 
uploads and downloads, add bot tokens to:

<code>WORKER_BOT_TOKENS</code>

<b>✨ Features</b>
• Parallel file transfers (faster speeds)
• Automatic failover on errors
• Intelligent load balancing
• Rate limit distribution
• Health monitoring & recovery

<i>Add tokens in config.env or via /bsettings</i>
"""


@new_task
async def worker_status(_, message):
    """Handle /workerstatus command."""
    
    if not TgClient.worker_pool or not TgClient.worker_pool.is_initialized:
        await send_message(message, _build_unconfigured_message())
        return
    
    pool = TgClient.worker_pool
    dispatcher = TgClient.dispatcher
    health_data = await pool.health_check()
    
    msg = _build_status_message(pool, dispatcher, health_data)
    
    buttons = ButtonMaker()
    buttons.data_button("🔄 Refresh", "workerstatus refresh")
    
    await send_message(message, msg, buttons.build_menu(1))


@new_task
async def worker_status_callback(_, query):
    """Handle callback for refresh button."""
    data = query.data.split()
    
    if len(data) < 2 or data[1] != "refresh":
        await query.answer("Unknown action", show_alert=True)
        return
    
    await query.answer("Refreshing...", show_alert=False)
    message = query.message
    
    if not TgClient.worker_pool or not TgClient.worker_pool.is_initialized:
        buttons = ButtonMaker()
        buttons.data_button("🔄 Refresh", "workerstatus refresh")
        try:
            await message.edit_text(
                _build_unconfigured_message(), 
                reply_markup=buttons.build_menu(1)
            )
        except Exception:
            pass
        return
    
    pool = TgClient.worker_pool
    dispatcher = TgClient.dispatcher
    health_data = await pool.health_check()
    
    msg = _build_status_message(pool, dispatcher, health_data)
    
    buttons = ButtonMaker()
    buttons.data_button("🔄 Refresh", "workerstatus refresh")
    
    try:
        await message.edit_text(msg, reply_markup=buttons.build_menu(1))
    except Exception:
        # Ignore MessageNotModified and other edit errors
        pass


def add_worker_status_handlers():
    """Register worker status command handlers."""
    TgClient.bot.add_handler(
        MessageHandler(
            worker_status,
            filters=command(BotCommands.WorkerStatusCommand) & CustomFilters.sudo
        )
    )
    
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            worker_status_callback,
            filters=regex(r"^workerstatus")
        )
    )
    
    LOGGER.info("Worker status handlers initialized")
