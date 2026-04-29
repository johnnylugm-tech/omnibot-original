import os
import re

files_to_fix = [
    ("app/api/__init__.py", ["import json", "import logging", "from typing import List", "from app.models import UnifiedResponse, EscalationRequest"]),
    ("app/security/__init__.py", ["from app.security.input_sanitizer import InputSanitizer", "from app.security.pii_masking import PIIMasking", "from app.security.prompt_injection import PromptInjectionDefense", "from app.security.prompt_injection import SecurityCheckResult", "from app.security.rate_limiter import RateLimiter", "from app.security.rbac import rbac", "from app.security.rate_limiter import TokenBucket", "from app.security.webhook_verifier import LineWebhookVerifier", "from app.security.webhook_verifier import TelegramWebhookVerifier", "from app.security.webhook_verifier import WebhookVerifier", "from app.security.webhook_verifier import get_verifier"]),
]

for file_path, lines_to_remove in files_to_fix:
    if not os.path.exists(file_path): continue
    with open(file_path, "r") as f:
        content = f.readlines()
    new_content = []
    for line in content:
        if any(rem in line for rem in lines_to_remove):
            continue
        new_content.append(line)
    with open(file_path, "w") as f:
        f.writelines(new_content)
