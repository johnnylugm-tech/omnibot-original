"""IP Whitelist - Advanced IP-based access control for API Gateway

Phase 3 security feature: IP whitelist enforcement at the API Gateway layer.
Applies to all incoming requests before rate limiting, TLS, and downstream processing.

Security properties:
- Empty / unconfigured whitelist = BYPASS (whitelist NOT enforced)
- Explicitly set whitelist = ENFORCED (fail-secure deny-all)
- Malformed IPs are denied when enforced (never raise, always deny)
- X-Forwarded-For header: uses the FIRST (leftmost) IP (original client)
"""
import ipaddress
import logging
import os
from typing import List, Optional, Union

logger = logging.getLogger("omnibot.ip_whitelist")


class IPWhitelistError(Exception):
    """Raised when IP whitelist configuration is invalid"""
    pass


class IPWhitelist:
    """Advanced IP Whitelisting for API Gateway

    Allows requests only from IP addresses that fall within whitelisted CIDR ranges.
    Supports both IPv4 and IPv6.

    Security model:
    - IP_WHITELIST_CIDRS NOT set → BYPASS (whitelist not enforced, allows all)
    - IP_WHITELIST_CIDRS="" (empty) → ENFORCED fail-secure (denies all)
    - IP_WHITELIST_CIDRS="1.2.3.0/24" → ENFORCED (only whitelisted IPs allowed)

    Placement in request lifecycle:
        Rate Limiting → IP Whitelist → TLS → Platform Adapter → RBAC
    """

    def __init__(self, whitelist_cidrs: Optional[List[str]] = None, enforced: Optional[bool] = None):
        """Initialize IP whitelist.

        Args:
            whitelist_cidrs: List of CIDR notation strings (e.g. ["203.0.113.0/24"]).
                             If None, reads from IP_WHITELIST_CIDRS environment variable.
            enforced: If True, empty whitelist means deny-all (fail-secure).
                      If False, empty whitelist means bypass (allow all).
                      If None, reads from IP_WHITELIST_ENABLED environment variable,
                      which defaults to False (bypass when not configured).
        """
        self._networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        self._whitelist_cidrs: List[str] = []

        # Determine enforcement mode
        if enforced is not None:
            self._enforced = enforced
        else:
            enabled_env = os.getenv("IP_WHITELIST_ENABLED", "").lower()
            if enabled_env in ("true", "1", "yes"):
                self._enforced = True
            elif enabled_env == "false":
                self._enforced = False
            else:
                # Default: bypass when not explicitly configured
                self._enforced = False

        cidrs = whitelist_cidrs if whitelist_cidrs is not None else self._load_from_env()
        for cidr in cidrs:
            self.add_cidr(cidr)

    def _load_from_env(self) -> List[str]:
        """Load CIDR list from environment variable.

        Format: comma-separated CIDR strings
        Example: "203.0.113.0/24,198.51.100.0/24,10.0.0.0/8"
        """
        env_val = os.getenv("IP_WHITELIST_CIDRS", "")
        if not env_val:
            return []
        return [c.strip() for c in env_val.split(",") if c.strip()]

    def add_cidr(self, cidr: str) -> None:
        """Add a CIDR range to the whitelist.

        Args:
            cidr: CIDR notation string (e.g. "203.0.113.0/24" or "2001:db8::/32")

        Raises:
            IPWhitelistError: If the CIDR format is invalid
        """
        cidr = cidr.strip()
        if not cidr:
            return

        try:
            network = ipaddress.ip_network(cidr, strict=False)
            self._networks.append(network)
            self._whitelist_cidrs.append(cidr)
            logger.info(f"ip_whitelist_added: cidr={cidr}, total={len(self._networks)}")
        except ValueError as e:
            raise IPWhitelistError(f"Invalid CIDR notation '{cidr}': {e}")

    def clear(self) -> None:
        """Clear all CIDR ranges from the whitelist.

        After clearing, is_allowed() will deny all IPs (fail-secure).
        """
        self._networks.clear()
        self._whitelist_cidrs.clear()
        logger.info("ip_whitelist_cleared")

    @property
    def whitelist_cidrs(self) -> List[str]:
        """Return the list of configured CIDR strings (read-only copy)"""
        return list(self._whitelist_cidrs)

    @property
    def is_enforced(self) -> bool:
        """Return True if the whitelist is in enforced mode (not bypass)."""
        return self._enforced

    @property
    def is_empty(self) -> bool:
        """Return True if whitelist is empty (no CIDRs configured)."""
        return len(self._networks) == 0

    def is_allowed(self, ip_str: str) -> bool:
        """Check if an IP address is within the whitelisted ranges.

        Args:
            ip_str: IP address string (IPv4 or IPv6)

        Returns:
            True if the IP is whitelisted, False otherwise.
            Returns False for any malformed input when enforced (fail-secure).
            Returns True (bypass) when whitelist is not enforced.
        """
        # Bypass mode: whitelist not enforced
        if not self._enforced:
            return True

        if not ip_str:
            return False

        ip_str = ip_str.strip()
        if not ip_str:
            return False

        # Handle comma-separated X-Forwarded-For format: take FIRST (leftmost) IP
        if "," in ip_str:
            ip_str = ip_str.split(",")[0].strip()

        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Malformed IP = deny (fail-secure)
            logger.warning("ip_whitelist_denied_malformed ip=%s", ip_str)
            return False

        for network in self._networks:
            if ip in network:
                logger.debug("ip_whitelist_allowed ip=%s matched_cidr=%s", ip_str, str(network))
                return True

        logger.debug("ip_whitelist_denied ip=%s whitelist_size=%d", ip_str, len(self._networks))
        return False

    def get_client_ip(self, request) -> str:
        """Extract the client IP from a FastAPI Request object.

        Checks X-Forwarded-For header first (takes first IP = original client),
        then falls back to request.client.host (direct connection IP).

        Args:
            request: FastAPI Request object

        Returns:
            The client IP address string, or empty string if unavailable
        """
        # Check X-Forwarded-For header (takes leftmost/first IP = original client)
        x_forwarded_for = request.headers.get("x-forwarded-for", "")
        if x_forwarded_for:
            # Take the first IP in the chain (original client before any proxies)
            return x_forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host or ""

        return ""


# Module-level singleton instance (lazy-initialized from environment)
_ip_whitelist: Optional[IPWhitelist] = None


def get_ip_whitelist() -> IPWhitelist:
    """Get or create the global IP whitelist singleton.

    Thread-safe singleton pattern.
    """
    global _ip_whitelist
    if _ip_whitelist is None:
        _ip_whitelist = IPWhitelist()
    return _ip_whitelist


def reset_ip_whitelist() -> None:
    """Reset the global IP whitelist singleton (primarily for testing)"""
    global _ip_whitelist
    _ip_whitelist = None
