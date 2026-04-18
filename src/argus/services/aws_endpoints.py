from __future__ import annotations
import os

# Maps boto3 service names to their FIPS endpoint host templates.
# FIPS endpoints are available in both commercial and GovCloud regions.
_FIPS_HOSTS: dict[str, str] = {
    "athena":    "athena-fips.{region}.amazonaws.com",
    "glue":      "glue-fips.{region}.amazonaws.com",
    "s3":        "s3-fips.{region}.amazonaws.com",
    "sts":       "sts-fips.{region}.amazonaws.com",
    "logs":      "logs-fips.{region}.amazonaws.com",
    "sso":       "portal.sso-fips.{region}.amazonaws.com",
    "sso-oidc":  "oidc-fips.{region}.amazonaws.com",
}


def fips_enabled() -> bool:
    """Return True when ARGUS_USE_FIPS_ENDPOINTS is set to a truthy value."""
    return os.environ.get("ARGUS_USE_FIPS_ENDPOINTS", "").lower() in ("1", "true", "yes")


def get_endpoint_url(service: str, region: str) -> str | None:
    """Return a FIPS-compliant endpoint URL for *service* in *region*, or None.

    Returns None (no override) when FIPS mode is disabled so boto3 uses its
    default endpoint resolution — ensuring zero behaviour change for standard
    (non-government) deployments.
    """
    if not fips_enabled():
        return None
    host = _FIPS_HOSTS.get(service)
    if host is None:
        return None
    return f"https://{host.format(region=region)}"
