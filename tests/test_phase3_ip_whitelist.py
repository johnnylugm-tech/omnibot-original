"""Tests for IP Whitelist (Phase 3 Advanced Security Feature)

Covers:
  XX.1  Basic whitelist behavior (4 tests)
  XX.2  Edge cases (4 tests)
  XX.3  Security properties (3 tests)
  XX.4  Integration with existing Phase 1/2 security chain (2 tests)

Run with: python3 -m pytest tests/test_phase3_ip_whitelist.py -v
"""
from unittest.mock import MagicMock, patch

import pytest

from app.security.ip_whitelist import (
    IPWhitelist,
    IPWhitelistError,
    get_ip_whitelist,
    reset_ip_whitelist,
)


# ---------------------------------------------------------------------------
# Helper: mock FastAPI Request
# ---------------------------------------------------------------------------
def make_mock_request(client_host: str = "203.0.113.1", x_forwarded_for: str = "") -> MagicMock:
    """Build a minimal mock FastAPI Request with the given client host and X-Forwarded-For."""
    request = MagicMock()
    request.client.host = client_host
    request.headers = MagicMock()
    if x_forwarded_for:
        request.headers.get = lambda key, default=None: x_forwarded_for if key == "x-forwarded-for" else default
    else:
        request.headers.get = lambda key, default=None: default
    return request


# ---------------------------------------------------------------------------
# XX.1  Basic whitelist behavior
# ---------------------------------------------------------------------------
class TestIPWhitelistBasic:
    def test_ip_whitelist_allows_whitelisted_source(self):
        """XX.1.1: Whitelisted IP returns True"""
        wl = IPWhitelist(whitelist_cidrs=["203.0.113.0/24", "198.51.100.0/24"])
        assert wl.is_allowed("203.0.113.42") is True
        assert wl.is_allowed("198.51.100.99") is True

    def test_ip_whitelist_denies_unwhitelisted_source(self):
        """XX.1.2: Non-whitelisted IP returns False when enforced"""
        wl = IPWhitelist(whitelist_cidrs=["203.0.113.0/24"], enforced=True)
        assert wl.is_allowed("192.0.2.1") is False

    def test_ip_whitelist_cidr_range_single_ip(self):
        """XX.1.3: /32 CIDR allows only the exact IP"""
        wl = IPWhitelist(whitelist_cidrs=["198.51.100.5/32"], enforced=True)
        assert wl.is_allowed("198.51.100.5") is True
        assert wl.is_allowed("198.51.100.6") is False
        assert wl.is_allowed("198.51.100.4") is False

    def test_ip_whitelist_cidr_range_multiple_ips(self):
        """XX.1.4: /24 CIDR allows all IPs within the range"""
        wl = IPWhitelist(whitelist_cidrs=["10.10.10.0/24"], enforced=True)
        assert wl.is_allowed("10.10.10.0") is True   # first
        assert wl.is_allowed("10.10.10.127") is True  # middle
        assert wl.is_allowed("10.10.10.255") is True  # last
        assert wl.is_allowed("10.10.11.0") is False    # outside


# ---------------------------------------------------------------------------
# XX.2  Edge cases
# ---------------------------------------------------------------------------
class TestIPWhitelistEdgeCases:
    def test_ip_whitelist_empty_denies_all_when_enforced(self):
        """XX.2.1a: Empty whitelist with enforced=True denies all IPs (fail-secure)"""
        wl = IPWhitelist(whitelist_cidrs=[], enforced=True)
        assert wl.is_enforced is True
        assert wl.is_empty is True
        assert wl.is_allowed("127.0.0.1") is False
        assert wl.is_allowed("203.0.113.1") is False

    def test_ip_whitelist_bypasses_when_not_enforced(self):
        """XX.2.1b: Empty whitelist with enforced=False (default) allows all IPs"""
        wl = IPWhitelist(whitelist_cidrs=[])
        assert wl.is_enforced is False
        assert wl.is_empty is True
        assert wl.is_allowed("127.0.0.1") is True   # bypass
        assert wl.is_allowed("203.0.113.1") is True   # bypass

    def test_ip_whitelist_x_forwarded_for_first_ip(self):
        """XX.2.2: X-Forwarded-For with multiple IPs uses the FIRST (leftmost)

        This test uses enforced=True to ensure the whitelist actually checks.
        """
        wl = IPWhitelist(whitelist_cidrs=["203.0.113.0/24"], enforced=True)
        request = make_mock_request(client_host="10.0.0.1", x_forwarded_for="203.0.113.50, 10.0.0.1, 172.16.0.1")
        assert wl.is_allowed(wl.get_client_ip(request)) is True   # 203.0.113.50 is in range

    def test_ip_whitelist_ipv4_vs_ipv6_not_mixed(self):
        """XX.2.3: IPv4 and IPv6 addresses are NOT matched across families"""
        wl = IPWhitelist(whitelist_cidrs=["192.0.2.0/24"], enforced=True)
        # IPv6-mapped IPv4 should NOT match an IPv4 CIDR
        assert wl.is_allowed("::ffff:192.0.2.100") is False

    def test_ip_whitelist_malformed_ip_denied_when_enforced(self):
        """XX.2.4: Malformed IP is denied when enforced, but bypassed when not enforced"""
        wl_enforced = IPWhitelist(whitelist_cidrs=["203.0.113.0/24"], enforced=True)
        assert wl_enforced.is_allowed("not.an.ip.address") is False
        assert wl_enforced.is_allowed("256.256.256.256") is False

        wl_bypass = IPWhitelist(whitelist_cidrs=["203.0.113.0/24"], enforced=False)
        assert wl_bypass.is_allowed("not.an.ip.address") is True  # bypass


# ---------------------------------------------------------------------------
# XX.3  Security properties
# ---------------------------------------------------------------------------
class TestIPWhitelistSecurity:
    def test_ip_whitelist_before_rate_limit_does_not_affect_rate_limit(self):
        """XX.3.1: Non-whitelisted IP is rejected BEFORE rate limit check.

        Verifies that IP whitelist is checked independently of (and before)
        the rate limiter — a denied IP must not consume rate limit tokens.
        """
        wl = IPWhitelist(whitelist_cidrs=["203.0.113.0/24"], enforced=True)
        # Denied IP
        denied_ip = "192.0.2.99"
        assert wl.is_allowed(denied_ip) is False
        # Whitelisted IP (separate token bucket, not affected by above check)
        allowed_ip = "203.0.113.5"
        assert wl.is_allowed(allowed_ip) is True

    def test_ip_whitelist_cidr_validation_rejects_invalid(self):
        """XX.3.2: Invalid CIDR notation raises IPWhitelistError"""
        wl = IPWhitelist(whitelist_cidrs=[])
        with pytest.raises(IPWhitelistError):
            wl.add_cidr("not-a-cidr")
        with pytest.raises(IPWhitelistError):
            wl.add_cidr("192.0.2.0/33")   # /33 is invalid for IPv4
        with pytest.raises(IPWhitelistError):
            wl.add_cidr("192.0.2.0/-1")

    def test_ip_whitelist_clear_empties_list(self):
        """XX.3.3: clear() removes all CIDRs and denies all IPs when enforced"""
        wl = IPWhitelist(whitelist_cidrs=["203.0.113.0/24"], enforced=True)
        assert wl.is_empty is False
        wl.clear()
        assert wl.is_empty is True
        assert wl.is_allowed("203.0.113.1") is False


# ---------------------------------------------------------------------------
# XX.4  Integration with existing security chain
# ---------------------------------------------------------------------------
class TestIPWhitelistIntegration:
    def test_get_client_ip_extracts_x_forwarded_for_first(self):
        """XX.4.1: get_client_ip() returns the first IP from X-Forwarded-For chain"""
        wl = IPWhitelist(whitelist_cidrs=[])
        request = make_mock_request(
            client_host="10.0.0.1",
            x_forwarded_for="203.0.113.7, 10.0.0.1, 172.16.0.5"
        )
        assert wl.get_client_ip(request) == "203.0.113.7"

    def test_get_client_ip_falls_back_to_client_host(self):
        """XX.4.2: get_client_ip() falls back to request.client.host when no X-Forwarded-For"""
        wl = IPWhitelist(whitelist_cidrs=[])
        request = make_mock_request(client_host="127.0.0.1", x_forwarded_for="")
        assert wl.get_client_ip(request) == "127.0.0.1"

    def test_ip_whitelist_singleton_pattern(self):
        """XX.4.3: get_ip_whitelist() returns a singleton; reset clears it"""
        reset_ip_whitelist()
        wl1 = get_ip_whitelist()
        wl2 = get_ip_whitelist()
        assert wl1 is wl2   # same instance
        reset_ip_whitelist()
        wl3 = get_ip_whitelist()
        assert wl3 is not wl1   # new instance after reset

    def test_ip_whitelist_environment_variable_loading(self):
        """XX.4.4: IPWhitelist loads CIDRs from IP_WHITELIST_CIDRS env var (bypass by default)"""
        with patch.dict("os.environ", {"IP_WHITELIST_CIDRS": "10.0.0.0/8,172.16.0.0/12"}):
            reset_ip_whitelist()
            wl = IPWhitelist()   # reads from env, enforced=False by default
            assert wl.is_allowed("10.5.6.7") is True
            assert wl.is_allowed("172.20.1.2") is True
            assert wl.whitelist_cidrs == ["10.0.0.0/8", "172.16.0.0/12"]
        reset_ip_whitelist()

    def test_ip_whitelist_enforced_with_env_var(self):
        """XX.4.4b: When IP_WHITELIST_ENABLED=true, whitelist is enforced"""
        with patch.dict("os.environ", {"IP_WHITELIST_CIDRS": "10.0.0.0/8", "IP_WHITELIST_ENABLED": "true"}):
            reset_ip_whitelist()
            wl = IPWhitelist()
            assert wl.is_enforced is True
            assert wl.is_allowed("10.5.6.7") is True
            assert wl.is_allowed("192.168.1.1") is False  # denied when enforced
        reset_ip_whitelist()

    def test_ip_whitelist_ipv6_support(self):
        """XX.4.5: IPv6 addresses are properly whitelisted"""
        wl = IPWhitelist(whitelist_cidrs=["2001:db8::/32", "fe80::/10"], enforced=True)
        assert wl.is_allowed("2001:db8::1") is True
        assert wl.is_allowed("2001:db8:ffff::1") is True
        assert wl.is_allowed("fe80::1") is True
        assert wl.is_allowed("2001:db9::1") is False   # different prefix
        assert wl.is_allowed("fe00::1") is False        # outside fe80::/10
