from __future__ import annotations
import re
from typing import Optional
from argus.models.schemas import AppConfig, NamingSchema


class NamingResolver:
    def __init__(
        self,
        schema: NamingSchema,
        assignments: Optional[dict[str, str]] = None,
    ):
        self.schema = schema
        self._pattern_re = _compile_pattern(schema.pattern, schema.client_id_regex)
        self._assignments: dict[str, str] = assignments or {}

    def parse_database_name(self, database_name: str) -> Optional[dict[str, str]]:
        """Extract named fields from a database name. Returns None if no match."""
        m = self._pattern_re.match(database_name)
        if m is None:
            return None
        return m.groupdict()

    def resolve_workgroup(self, database_name: str) -> Optional[str]:
        """Return the explicitly assigned workgroup, or None (→ Unassigned)."""
        return self._assignments.get(database_name)

    def get_client_id(self, database_name: str) -> Optional[str]:
        parts = self.parse_database_name(database_name)
        if parts is None:
            return None
        return parts.get("client_id")


def _compile_pattern(pattern: str, client_id_regex: str) -> re.Pattern:
    """Convert a {field} pattern string to a compiled regex."""
    fields = re.findall(r"\{(\w+)\}", pattern)

    regex = re.escape(pattern)
    for field in fields:
        if field == "client_id":
            group_regex = f"(?P<{field}>{client_id_regex})"
        else:
            group_regex = f"(?P<{field}>[^_]+)"
        regex = regex.replace(re.escape(f"{{{field}}}"), group_regex, 1)

    return re.compile(f"^{regex}$")


def get_resolver(config: AppConfig, schema_name: Optional[str] = None) -> Optional[NamingResolver]:
    name = schema_name or config.active_schema
    schema = config.naming_schemas.get(name)
    if schema is None:
        return None
    assignments = config.workgroups.assignments if config.workgroups else {}
    return NamingResolver(schema, assignments)
