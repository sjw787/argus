from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class NamingSchema(BaseModel):
    """Defines how to parse database names and resolve workgroup names."""
    pattern: str
    client_id_regex: str
    workgroup_pattern: str
    description: Optional[str] = None


class WorkgroupConfig(BaseModel):
    output_locations: dict[str, str] = Field(default_factory=dict)
    assignments: dict[str, str] = Field(default_factory=dict)
    """Explicit database → workgroup assignments. Databases not listed here are Unassigned."""


class AWSConfig(BaseModel):
    region: str = "us-east-1"
    profile: Optional[str] = None


class DefaultsConfig(BaseModel):
    output_location: Optional[str] = None
    max_results: int = 100
    query_timeout_seconds: int = 300


class AppConfig(BaseModel):
    aws: AWSConfig = Field(default_factory=AWSConfig)
    naming_schemas: dict[str, NamingSchema] = Field(default_factory=dict)
    active_schema: str = "default"
    workgroups: WorkgroupConfig = Field(default_factory=WorkgroupConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    auth_mode: str = "sso"
    locked_settings: list[str] = Field(
        default_factory=list,
        description=(
            "Settings keys that users cannot change. Valid values: "
            "theme, sqlAutocomplete, sqlDiagnostics, showHistoryDefault, "
            "showInformationSchema, formatStyle, autoLimit"
        ),
    )
