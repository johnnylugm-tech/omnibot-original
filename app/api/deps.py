"""Shared FastAPI dependencies — single instance per process."""

import os

from app.security import (
    InputSanitizer,
    PIIMasking,
    PromptInjectionDefense,
    RateLimiter,
    get_ip_whitelist,
)
from app.security import (
    get_verifier as get_verifier,
)
from app.security import (
    rbac as rbac,
)
from app.security.encryption import EncryptionService
from app.services.backup import BackupService
from app.services.degradation import DegradationManager
from app.services.dst import DSTManager
from app.utils.alerts import AlertManager
from app.utils.cost_model import CostModel
from app.utils.logger import StructuredLogger

# ── Instantiate once at module load ──────────────────────────────────────────
sanitizer = InputSanitizer()
pii_masking = PIIMasking()
prompt_defense = PromptInjectionDefense()
rate_limiter = RateLimiter()
ip_whitelist = get_ip_whitelist()
dst_manager = DSTManager()
degradation_manager = DegradationManager()
encryption_service = EncryptionService()
alert_manager = AlertManager()
cost_model = CostModel()
backup_service = BackupService()
logger = StructuredLogger("omnibot")

# ── Environment variables ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
MESSENGER_APP_SECRET = os.getenv("MESSENGER_APP_SECRET", "messenger_secret")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "whatsapp_secret")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DAILY_COST_CAP = float(os.getenv("DAILY_COST_CAP", "50.0"))
