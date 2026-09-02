"""Centralized presentation settings for the customized FileHub build.

Keep user-facing names and project links here so modules do not hard-code
branding details. Runtime secrets and deployment credentials must remain in
Config / environment variables, not in this module.
"""

APP_NAME = "FileHub"
APP_TAGLINE = "Unified download, processing and cloud transfer bot"
REPOSITORY_URL = "https://github.com/RecklessEvadingDriver/mirror-leech-telegram-bot"

FEATURE_SUMMARY = (
    "Direct links • Telegram files • Torrents • NZB • yt-dlp • gallery-dl • "
    "Google Drive • rclone • Telegram uploads"
)

AUTHORIZED_WELCOME = (
    "<b>🚀 {name}</b>\n"
    "<i>{tagline}</i>\n\n"
    "<b>Supported workflows</b>\n"
    "• Download from links, Telegram, torrents and NZB\n"
    "• Mirror to Google Drive or rclone remotes\n"
    "• Leech files back to Telegram\n"
    "• Download media with yt-dlp and gallery-dl\n"
    "• Track, queue, select and cancel active tasks\n\n"
    "Use /{help_command} for commands and usage details."
)

UNAUTHORIZED_WELCOME = (
    "<b>🔒 {name}</b>\n"
    "<i>{tagline}</i>\n\n"
    "This instance is private and your account/chat is not authorized.\n"
    "Ask the bot administrator for access or deploy your own instance."
)
