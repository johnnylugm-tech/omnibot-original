# Design: Fixing Remaining Linting Errors in Omnibot

## Goal
Resolve all remaining linting errors (~490) in the `/Users/johnny/omnibot-original` project, specifically focusing on `E501` (Line too long) and `F401` (Unused import).

## Current Status
- Total errors: ~491
- Most common: `E501`, `F401`, `E402`, `I001`, `N802`.
- `ruff check . --fix` has been run but many errors remain because they require manual intervention or specific formatting.

## Proposed Approach

### 1. Resolve `F401` (Unused Imports)
- Many `F401` errors in `app/security/__init__.py` are due to re-exports not using explicit aliases (e.g., `from .module import Symbol as Symbol`).
- I will update `app/security/__init__.py` to use explicit aliases for re-exports.
- Other `F401` errors in test files will be removed manually if they are truly unused.

### 2. Resolve `E501` (Line Too Long)
- I will manually wrap lines exceeding 88 characters.
- Priority files:
    - `app/api/__init__.py`
    - `tests/test_phase3_observability.py`
    - `tests/test_phase3_rbac_ab.py`
- Strategy:
    - Break long function signatures into multiple lines.
    - Break long `select` statements or method calls.
    - Break long strings or comments.

### 3. Resolve `I001` (Import Sorting)
- Run `ruff check . --select I001 --fix` to automatically sort import blocks.

### 4. Resolve `E402` (Module level import not at top of file)
- Move imports to the top of the file in `tests/test_phase3_rbac_ab.py`.

### 5. Resolve `N802` (Function name should be lowercase)
- Rename `test_token_expired_returns_401_AUTH_TOKEN_EXPIRED` to `test_token_expired_returns_401_auth_token_expired` in `tests/test_phase3_rbac_security.py`.

### 6. Resolve `E722` (Bare except)
- Change `except:` to `except Exception:` in `tests/test_phase4_red_team.py`.

## Validation Plan
1. Run `ruff check .` after changes to ensure 0 errors.
2. Run `pytest` to ensure all tests still pass.

## Success Criteria
- `ruff check .` returns 0 errors.
- `pytest` returns 100% pass (excluding known skips).
- Python 3.9 compatibility maintained.
