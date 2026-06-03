"""Timezone constants for the application.

WIB (Waktu Indonesia Barat) = UTC+7
Used for all display and scheduling.
"""
from datetime import timezone, timedelta

WIB = timezone(timedelta(hours=7))  # Asia/Jakarta
