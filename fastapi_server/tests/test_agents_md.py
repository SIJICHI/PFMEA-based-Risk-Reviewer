# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests to validate that the paths and references mentioned in AGENTS.md
actually exist in the codebase.

WHY THESE TESTS EXIST:
The AGENTS.md file provides instructions to AI agents and developers about
where to find and add code in the project. If the paths referenced in AGENTS.md
are incorrect or outdated, agents will fail to complete tasks correctly.
These tests ensure the documentation stays in sync with the actual project structure.
"""

from pathlib import Path

# Get the fastapi_server root directory
FASTAPI_SERVER_ROOT = Path(__file__).parent.parent


def test_agents_md_paths_exist() -> None:
    """
    Verify that the paths referenced in AGENTS.md actually exist.

    Required by AGENTS.md

    If this test fails, either the paths were moved/deleted and AGENTS.md needs
    updating, or the paths need to be restored to match the documentation.
    """
    # Check that fastapi_server/app/main.py exists
    main_py = FASTAPI_SERVER_ROOT / "app" / "main.py"
    assert main_py.exists() and main_py.is_file(), (
        "fastapi_server/app/main.py should exist. "
        "AGENTS.md references this as the backend entry point."
    )

    # Check that fastapi_server/app/api/v1 exists
    api_v1_dir = FASTAPI_SERVER_ROOT / "app" / "api" / "v1"
    assert api_v1_dir.exists() and api_v1_dir.is_dir(), (
        "fastapi_server/app/api/v1 should exist. "
        "AGENTS.md references this as the location for new endpoints."
    )
