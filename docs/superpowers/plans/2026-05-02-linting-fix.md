# Linting Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all remaining linting errors (~490) in the Omnibot project.

**Architecture:** Use `ruff` to identify and automatically fix issues where possible, then manually wrap long lines (E501) and update re-exports (F401) to follow best practices.

**Tech Stack:** Python 3.9, ruff, pytest.

---

### Task 1: Fix Unused Imports in app/security/__init__.py (F401)

**Files:**
- Modify: `app/security/__init__.py`

- [ ] **Step 1: Update re-exports with explicit aliases**

Modify `app/security/__init__.py` to use `as Symbol` for each import.

```python
from .input_sanitizer import InputSanitizer as InputSanitizer
from .ip_whitelist import (
    IPWhitelist as IPWhitelist,
    IPWhitelistError as IPWhitelistError,
    get_ip_whitelist as get_ip_whitelist,
    reset_ip_whitelist as reset_ip_whitelist,
)
from .pii_masking import PIIMasking as PIIMasking
from .prompt_injection import PromptInjectionDefense as PromptInjectionDefense, SecurityCheckResult as SecurityCheckResult
from .rate_limiter import RateLimiter as RateLimiter, TokenBucket as TokenBucket
from .rbac import RBACEnforcer as RBACEnforcer, rbac as rbac
from .webhook_verifier import (
    LineWebhookVerifier as LineWebhookVerifier,
    MessengerWebhookVerifier as MessengerWebhookVerifier,
    TelegramWebhookVerifier as TelegramWebhookVerifier,
    WebhookVerifier as WebhookVerifier,
    WhatsAppWebhookVerifier as WhatsAppWebhookVerifier,
    get_verifier as get_verifier,
)
```

- [ ] **Step 2: Verify F401 is resolved in this file**

Run: `ruff check app/security/__init__.py`
Expected: 0 errors for this file.

- [ ] **Step 3: Commit**

```bash
git add app/security/__init__.py
git commit -m "style: use explicit re-exports in app/security/__init__.py to fix F401"
```

---

### Task 2: Fix Imports and Formatting in tests/test_phase3_rbac_ab.py (E402, E501)

**Files:**
- Modify: `tests/test_phase3_rbac_ab.py`

- [ ] **Step 1: Move imports to top of file and wrap long lines**

```python
# Move imports from line 4-12 to the top
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request

from app.security.rbac import RBACEnforcer
from app.services.ab_test import ABTestManager
from app.utils.tracing import setup_tracing, tracer
```

- [ ] **Step 2: Wrap long lines manually**

Find lines longer than 88 characters and wrap them using parentheses or multiline strings.

- [ ] **Step 3: Verify E402 and E501 are resolved**

Run: `ruff check tests/test_phase3_rbac_ab.py`
Expected: Significant reduction in errors for this file.

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase3_rbac_ab.py
git commit -m "style: fix E402 and E501 in tests/test_phase3_rbac_ab.py"
```

---

### Task 3: Fix N802 and E501 in tests/test_phase3_rbac_security.py

**Files:**
- Modify: `tests/test_phase3_rbac_security.py`

- [ ] **Step 1: Rename function to lowercase**

```python
# Change
def test_token_expired_returns_401_AUTH_TOKEN_EXPIRED(...):
# To
def test_token_expired_returns_401_auth_token_expired(...):
```

- [ ] **Step 2: Wrap long lines**

Wrap long lines in this file.

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase3_rbac_security.py
git commit -m "style: fix N802 and E501 in tests/test_phase3_rbac_security.py"
```

---

### Task 4: Fix E501 in app/api/__init__.py

**Files:**
- Modify: `app/api/__init__.py`

- [ ] **Step 1: Manually wrap long lines**

Identify and fix all E501 errors in `app/api/__init__.py`. Use parentheses for line continuation in function calls and definitions.

- [ ] **Step 2: Commit**

```bash
git add app/api/__init__.py
git commit -m "style: fix E501 in app/api/__init__.py"
```

---

### Task 5: Final Global Cleanup and Verification

- [ ] **Step 1: Run global import sorting**

Run: `ruff check . --select I001 --fix`

- [ ] **Step 2: Run remaining E501 fixes across codebase**

Manually visit remaining files reported by `ruff check .` and fix E501 errors.

- [ ] **Step 3: Run final ruff check**

Run: `ruff check .`
Expected: 0 errors.

- [ ] **Step 4: Run all tests**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 5: Final Commit**

```bash
git commit -m "style: resolve all remaining linting errors"
```
