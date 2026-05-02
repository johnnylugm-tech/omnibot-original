# Omnibot Linting Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Achieve zero linting errors in the Omnibot project using `ruff`.

**Architecture:** Hybrid approach using `ruff format`, `ruff check --fix --unsafe-fixes`, and targeted manual wrapping/renaming.

**Tech Stack:** Ruff (Linter/Formatter), Python.

---

### Task 1: Baseline & Automated Formatting

**Files:**
- Modify: All files in `/Users/johnny/omnibot-original`

- [ ] **Step 1: Run ruff format**
Run: `ruff format .`
Expected: Reduces E501 count significantly.

- [ ] **Step 2: Run ruff check with unsafe fixes**
Run: `ruff check . --fix --unsafe-fixes`
Expected: Fixes E402, F401, W291 automatically.

- [ ] **Step 3: Verify remaining errors**
Run: `ruff check . --statistics`
Expected: Significantly fewer than 192 errors.

---

### Task 2: Fix N802 (Invalid function name)

**Files:**
- Modify: Files reported with N802 (e.g., CamelCase methods)

- [ ] **Step 1: Identify N802 locations**
Run: `ruff check . --select N802`

- [ ] **Step 2: Rename functions to snake_case**
Example change:
```python
# Old
def myFunctionName():
    pass

# New
def my_function_name():
    pass
```
*Note: Ensure all callers are updated.*

---

### Task 3: Fix N806 (Non-lowercase variable in function)

**Files:**
- Modify: Files reported with N806

- [ ] **Step 1: Rename local variables to snake_case**
Example change:
```python
# Old
def func():
    MyVar = 1

# New
def func():
    my_var = 1
```

---

### Task 4: Fix E722 (Bare except)

**Files:**
- Modify: Files reported with E722

- [ ] **Step 1: Add Exception type to bare excepts**
```python
# Old
try:
    ...
except:
    ...

# New
try:
    ...
except Exception:
    ...
```

---

### Task 5: Manual E501 Resolution (Residuals)

**Files:**
- Modify: Files with remaining E501

- [ ] **Step 1: Wrap long strings/comments**
For strings: Use `("part 1" "part 2")` implicit concatenation.
For URLs/Regex: Use `# noqa: E501` if wrapping is impossible.

---

### Task 6: Final Verification

- [ ] **Step 1: Final ruff check**
Run: `ruff check .`
Expected: "All checks passed!"

- [ ] **Step 2: Run tests**
Run: `pytest`
Expected: All tests pass.
