from __future__ import annotations

# Test-facing compatibility shim. The shared implementation now lives under
# sqlopt.devtools so repo scripts no longer import from tests/.
from sqlopt.devtools.fixture_project import *  # noqa: F401,F403
