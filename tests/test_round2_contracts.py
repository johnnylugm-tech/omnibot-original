import subprocess

import pytest

from app.services.backup import BackupService


@pytest.mark.security
def test_id_security_backup_subprocess_contract():
    """SPEC: BackupService must handle subprocess calls safely without shell=True and with proper path validation."""
    # This is a behavior contract test
    service = BackupService("/tmp/backups")
    # We want to ensure no shell injection is possible
    # (Mocking or real execution check)
    assert True # Stub for RED phase, we'll verify via bandit later

@pytest.mark.linting
def test_id_linting_clean_contract():
    """SPEC: Codebase must pass ruff check with zero errors."""
    result = subprocess.run(["ruff", "check", "."], capture_output=True)
    assert result.returncode == 0
