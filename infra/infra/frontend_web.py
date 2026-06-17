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

import hashlib
from pathlib import Path

import pulumi
import pulumi_command as command
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME

project_dir = Path(__file__).parent.parent.parent

FRONTEND_SOURCE_GLOBS = [
    "src/**/*",
    "public/**/*",
    "package.json",
    "package-lock.json",
    "index.html",
    "tsconfig*.json",
    "vite.config.*",
    "tailwind.config.*",
    "postcss.config.*",
    "eslint.config.*",
    "components.json",
    ".prettierrc*",
    ".npmrc",
]


def _hash_frontend_sources(frontend_dir: Path) -> str:
    """Compute a single SHA-256 over all frontend source files."""
    h = hashlib.sha256()
    files: list[Path] = []
    for pattern in FRONTEND_SOURCE_GLOBS:
        files.extend(frontend_dir.glob(pattern))
    for file_path in sorted(set(files)):
        if file_path.is_file():
            h.update(str(file_path.relative_to(frontend_dir)).encode())
            h.update(file_path.read_bytes())
    return h.hexdigest()


def build_frontend() -> command.local.Command:
    """
    Build the frontend application before deploying infrastructure.
    Only rebuilds when source files change.
    """
    frontend_dir = project_dir / "frontend_web"
    source_hash = _hash_frontend_sources(frontend_dir)

    build_react_app = command.local.Command(
        f"Agentic Application Starter [{PROJECT_NAME}] Build Frontend",
        create=f"cd {frontend_dir} && npm install && npm run build",
        triggers=[source_hash],
        opts=pulumi.ResourceOptions(depends_on=[]),
    )

    return build_react_app


frontend_web = build_frontend()

__all__ = ["frontend_web"]
