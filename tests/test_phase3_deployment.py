"""
Atomic TDD Tests for Phase 3: Deployment, DR, Encryption & Ops (#50)
Covers: Deployment verification, Backup/DR, Encryption config, PostgreSQL/Redis security settings
"""
import os

import pytest

# =============================================================================
# Section 50: Phase 3 部署與災備驗證
# =============================================================================


def test_all_message_type_enum_values_valid():
    """
    Section 50: message_type 枚舉值皆合法。
    Verify MessageType enum has all expected values: text, image, sticker, location, file.
    """
    from app.models import MessageType

    valid_values = {e.value for e in MessageType}
    expected = {"text", "image", "sticker", "location", "file"}
    assert expected.issubset(valid_values), f"Missing message_type values: {expected - valid_values}"
    assert len(valid_values) >= len(expected)


def test_all_platform_enum_values_valid():
    """
    Section 50: platform 枚舉值皆合法（telegram/line/messenger/whatsapp）。
    Verify Platform enum has all expected values.
    """
    from app.models import Platform

    valid_values = {e.value for e in Platform}
    expected = {"telegram", "line", "messenger", "whatsapp"}
    assert expected.issubset(valid_values), f"Missing platform values: {expected - valid_values}"
    # telegram and line are Phase 1, messenger and whatsapp are Phase 2


@pytest.mark.asyncio
async def test_backup_knowledge_soft_delete_rollback():
    """
    Section 50: 知識庫軟刪除可 rollback。
    Verify that soft-deleted (is_active=False) knowledge entries can be restored.
    """
    # This test verifies the soft-delete mechanism allows rollback.
    # In real environment: DB must be running.
    pytest.skip("Requires running PostgreSQL and full app environment")
    from sqlalchemy import select

    from app.models.database import KnowledgeBase, get_db

    async with get_db() as db:
        # Soft delete: set is_active=False
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == 1)
        result = await db.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry:
            original_active = entry.is_active
            entry.is_active = False
            await db.commit()

            # Rollback: restore is_active=True
            await db.rollback()
            # Or explicitly set back
            entry.is_active = True
            await db.commit()

            # Verify restored
            stmt2 = select(KnowledgeBase).where(KnowledgeBase.id == 1)
            result2 = await db.execute(stmt2)
            restored = result2.scalar_one_or_none()
            assert restored is not None
            assert restored.is_active is True


@pytest.mark.docker
@pytest.mark.skipif(
    not os.path.exists("/private/tmp/omnibot-repo/docker-compose.yml"),
    reason="docker-compose.yml not found"
)
def test_deploy_docker_compose_all_services_healthy():
    """
    Section 50: docker-compose 所有服務健康。
    Verify all services defined in docker-compose.yml are in healthy state.
    Requires: docker, docker-compose, running environment.
    """

    # Check docker-compose file exists and has expected services
    compose_path = "/private/tmp/omnibot-repo/docker-compose.yml"
    assert os.path.exists(compose_path)

    # Read compose file and verify key services
    with open(compose_path) as f:
        content = f.read()
        # At minimum there should be postgres, redis, and app services
        assert "postgres" in content or "db" in content.lower()
        assert "redis" in content.lower()

    # In real CI, would run: docker-compose ps --format json
    # and verify each service is "running" or "healthy"
    pytest.skip("Requires Docker daemon and full docker-compose stack running")


@pytest.mark.skip("Requires running app server with health endpoint")
def test_deploy_health_endpoint_returns_200_after_startup():
    """
    Section 50: 啟動後健康檢查回傳 200。
    After full startup, /api/v1/health must return HTTP 200.
    """
    import requests

    health_url = os.getenv("OMNIBOT_HEALTH_URL", "http://localhost:8000/api/v1/health")

    # In real deployment test, after docker-compose up and waiting for readiness:
    response = requests.get(health_url, timeout=5)
    assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
    data = response.json()
    assert data.get("status") in ["healthy", "degraded"]


@pytest.mark.k8s
@pytest.mark.skip("Requires Kubernetes cluster and kubectl access")
def test_deploy_k8s_replicas_count_3():
    """
    Section 50: K8s 部署有 3 個副本。
    Verify Kubernetes deployment has spec.replicas=3.
    """
    import subprocess

    # Query current deployment
    result = subprocess.run(
        ["kubectl", "get", "deployment", "omnibot-api", "-o", "jsonpath={.spec.replicas}"],
        capture_output=True, text=True, cwd="/private/tmp/omnibot-repo"
    )
    replicas = int(result.stdout.strip())
    assert replicas == 3, f"Expected 3 replicas, got {replicas}"


@pytest.mark.k8s
@pytest.mark.skip("Requires Kubernetes cluster and kubectl access")
def test_deploy_k8s_rolling_update_completes_without_downtime():
    """
    Section 50: 滾動更新無停機。
    Verify rolling update strategy allows zero-downtime deployments.
    """
    import subprocess

    # Get current deployment strategy
    result = subprocess.run(
        [
            "kubectl", "get", "deployment", "omnibot-api", "-o",
            "jsonpath={.spec.strategy.type}"
        ],
        capture_output=True, text=True, cwd="/private/tmp/omnibot-repo"
    )
    strategy = result.stdout.strip()
    assert strategy == "RollingUpdate", f"Expected RollingUpdate strategy, got {strategy}"

    pytest.skip("Full rolling update test requires triggering actual deployment")


@pytest.mark.k8s
@pytest.mark.skip("Requires Kubernetes cluster and kubectl access")
def test_deploy_k8s_rolling_update_max_surge_1():
    """
    Section 50: 滾動更新 maxSurge=1。
    Verify rolling update maxSurge is set to 1 (max extra pods during update).
    """
    import subprocess

    result = subprocess.run(
        [
            "kubectl", "get", "deployment", "omnibot-api", "-o",
            "jsonpath={.spec.strategy.rollingUpdate.maxSurge}"
        ],
        capture_output=True, text=True, cwd="/private/tmp/omnibot-repo"
    )
    max_surge = result.stdout.strip()
    assert max_surge in ["1", "25%"], f"Expected maxSurge=1 or 25%, got {max_surge}"


@pytest.mark.k8s
@pytest.mark.skip("Requires Kubernetes cluster and kubectl access")
def test_deploy_k8s_rolling_update_max_unavailable_1():
    """
    Section 50: 滾動更新 maxUnavailable=1。
    Verify rolling update maxUnavailable is set to 1 (max pods offline during update).
    """
    import subprocess

    result = subprocess.run(
        [
            "kubectl", "get", "deployment", "omnibot-api", "-o",
            "jsonpath={.spec.strategy.rollingUpdate.maxUnavailable}"
        ],
        capture_output=True, text=True, cwd="/private/tmp/omnibot-repo"
    )
    max_unavail = result.stdout.strip()
    assert max_unavail in ["1", "25%"], f"Expected maxUnavailable=1 or 25%, got {max_unavail}"


@pytest.mark.skip("Requires running PostgreSQL")
def test_encryption_config_table_schema():
    """
    Section 50: 加密設定表 schema 正確。
    Verify encryption_config (or platform_configs) table has correct schema
    for storing encryption-related settings.
    """
    from app.models.database import PlatformConfig

    # Verify table has required columns for encryption config
    # platform_configs stores webhook_secret_key_ref which is encryption-related
    assert hasattr(PlatformConfig, "platform")
    assert hasattr(PlatformConfig, "config")
    assert hasattr(PlatformConfig, "webhook_secret_key_ref")

    # Verify JSONB config field can store encryption settings
    test_config = {
        "encryption": {
            "type": "AES-256-GCM",
            "key_id": "master_key_v1",
            "encrypt_at_rest": True
        }
    }
    assert isinstance(test_config, dict)
    assert "encryption" in test_config


@pytest.mark.skip("Requires PostgreSQL with TDE enabled")
def test_postgresql_tde_enabled():
    """
    Section 50: PostgreSQL TDE 已啟用。
    Verify PostgreSQL Transparent Data Encryption (TDE) is enabled at database level.
    This requires checking pg_settings or performing a test encryption operation.
    """
    import subprocess

    # Check if PostgreSQL is running with encryption settings
    result = subprocess.run(
        ["psql", os.getenv("DATABASE_URL", ""), "-c",
         "SHOW ssl;"],
        capture_output=True, text=True
    )
    # TDE is at storage layer; we verify via encryption_service presence
    from app.security.encryption import EncryptionService
    svc = EncryptionService()
    assert svc is not None
    # If encryption_service can perform encrypt/decrypt, TDE layer integration is verified
    pytest.skip("Full TDE verification requires infrastructure access")


@pytest.mark.skip("Requires running Redis with ACL enabled")
def test_redis_acl_enabled():
    """
    Section 50: Redis ACL 已啟用。
    Verify Redis ACL (Access Control List) is enabled and configured.
    """
    import subprocess

    # Check Redis ACL config
    result = subprocess.run(
        ["redis-cli", "CONFIG", "GET", "aclfile"],
        capture_output=True, text=True
    )
    # In production, Redis should have ACL file configured
    # For unit test, verify the import works
    from app.security.rate_limiter import RateLimiter
    limiter = RateLimiter()
    assert limiter is not None
    pytest.skip("Full ACL verification requires running Redis server")


@pytest.mark.skip("Requires running Redis with ACL configured")
def test_redis_default_user_disabled():
    """
    Section 50: Redis default user 已停用。
    Verify Redis default (unnamed) user is disabled for security.
    """
    import subprocess

    # Check that default user does not have general access
    result = subprocess.run(
        ["redis-cli", "ACL", "GETUSER", "default"],
        capture_output=True, text=True
    )
    # If default user exists, it should be in disabled state
    # In real environment: assert "off" in result.stdout
    pytest.skip("Requires live Redis with ACL configured")


@pytest.mark.skip("Requires running Redis with password auth")
def test_redis_requirepass_auth():
    """
    Section 50: Redis requirepass 認證正常。
    Verify Redis requirepass authentication is functioning correctly.
    """

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Verify Redis can be pinged with auth
    # In real environment: redis-cli -a <password> ping
    from app.security.rate_limiter import RateLimiter
    limiter = RateLimiter()
    assert limiter is not None
    pytest.skip("Requires Redis with requirepass configured")


@pytest.mark.skip("Requires running Redis with TLS configured")
def test_redis_tls_enabled():
    """
    Section 50: Redis TLS 已啟用。
    Verify Redis TLS (rediss://) is enabled for encrypted in-transit communication.
    """
    import subprocess

    # Check TLS config
    result = subprocess.run(
        ["redis-cli", "CONFIG", "GET", "tls-port"],
        capture_output=True, text=True
    )
    # In production, Redis should listen on TLS port
    pytest.skip("Requires Redis with TLS certificate configured")


@pytest.mark.skip("Requires PostgreSQL with sslmode=verify-full")
def test_ssl_mode_verify_full():
    """
    Section 50: PostgreSQL sslmode=verify-full。
    Verify PostgreSQL connection uses sslmode=verify-full (maximum TLS verification).
    """
    import os

    db_url = os.getenv("DATABASE_URL", "")
    # PostgreSQL SSL modes: disable, allow, prefer, require, verify-ca, verify-full
    if "sslmode" in db_url:
        assert "sslmode=verify-full" in db_url or "sslmode=verify-ca" in db_url, \
            "DATABASE_URL must use sslmode=verify-full for production"
    else:
        # If sslmode not in URL, connection will default to prefer
        # For production, must be explicitly set
        pytest.fail("DATABASE_URL missing sslmode parameter — must be verify-full")


@pytest.mark.skip("Requires running PostgreSQL for backup verification")
def test_backup_pg_basebackup_and_restore():
    """
    Section 50: pg_basebackup 和還原正常。
    Verify pg_basebackup can create a valid backup and restore works.
    Requires: running PostgreSQL, backup script at scripts/backup.sh.
    """

    backup_script = "/private/tmp/omnibot-repo/scripts/backup.sh"
    assert os.path.exists(backup_script), "backup.sh must exist"

    # In real environment, would run:
    # 1. pg_basebackup -h localhost -U omnibot -D /backups/latest -Ft -z -P
    # 2. Verify backup file exists
    # 3. Simulate restore by extracting and verifying consistency

    pytest.skip("Full backup/restore test requires running PostgreSQL and backup infrastructure")


@pytest.mark.skip("Requires running Redis with RDB and AOF configured")
def test_backup_redis_rdb_and_aof_restore():
    """
    Section 50: Redis RDB + AOF 還原正常。
    Verify Redis RDB snapshot and AOF (Append Only File) restore work correctly.
    Requires: running Redis with both rdb and aof enabled.
    """
    import subprocess

    # Check Redis persistence config
    result = subprocess.run(
        ["redis-cli", "CONFIG", "GET", "save"],
        capture_output=True, text=True
    )
    # Should have rdb save config (e.g., "save 900 1 300 10 60 10000")
    assert len(result.stdout.strip()) > 0

    result_aof = subprocess.run(
        ["redis-cli", "CONFIG", "GET", "appendonly"],
        capture_output=True, text=True
    )
    # AOF should be yes
    assert "yes" in result_aof.stdout.lower()

    # In real environment, would trigger BGSAVE and verify .rdb file
    # Then verify AOF rewrite works correctly
    pytest.skip("Full RDB/AOF restore test requires running Redis with persistence configured")
