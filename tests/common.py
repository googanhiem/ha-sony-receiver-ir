"""Test helpers that work with both Home Assistant test plugins.

Home Assistant 2026.11+ publishes ``pytest-homeassistant``; older releases
are tested with ``pytest-homeassistant-custom-component``.
"""

try:
    from pytest_homeassistant.common import MockConfigEntry, mock_restore_cache
except ImportError:
    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry,
        mock_restore_cache,
    )

__all__ = ["MockConfigEntry", "mock_restore_cache"]
