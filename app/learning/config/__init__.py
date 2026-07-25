"""Configuration Management — immutable snapshots, pointer-based rollback, diffs."""

from .models import ConfigurationSnapshot, ConfigDiff, ConfigDomain
from .manager import ConfigManager

__all__ = ["ConfigurationSnapshot", "ConfigDiff", "ConfigDomain", "ConfigManager"]
