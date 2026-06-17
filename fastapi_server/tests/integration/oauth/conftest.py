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

"""Pytest fixtures for OAuth integration tests."""

import os
from typing import Generator

import pytest
import requests


@pytest.fixture(scope="session")
def mock_oauth_url() -> str:
    """Base URL for the mock OAuth2 server."""
    return os.getenv("MOCK_OAUTH_URL", "http://localhost:18881")


@pytest.fixture(scope="session")
def app_url() -> str:
    """Base URL for the application under test."""
    return os.getenv("APP_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def mock_oauth_server_available(mock_oauth_url: str) -> bool:
    """Check if mock OAuth2 server is available for all configured providers."""
    providers = ["google", "microsoft"]
    try:
        for provider in providers:
            response = requests.get(
                f"{mock_oauth_url}/{provider}/.well-known/openid-configuration",
                timeout=5,
            )
            if response.status_code != 200:
                return False
        return True
    except requests.RequestException:
        return False


@pytest.fixture(scope="session")
def app_available(app_url: str) -> bool:
    """Check if application is available."""
    try:
        response = requests.get(app_url, timeout=5)
        return bool(response.status_code == 200)
    except requests.RequestException:
        return False


@pytest.fixture(autouse=True)
def require_mock_oauth_server(
    request: pytest.FixtureRequest, mock_oauth_server_available: bool
) -> Generator[None, None, None]:
    """Skip test if mock OAuth server is not available."""
    if not mock_oauth_server_available:
        pytest.skip("Mock OAuth2 server not available")
    yield


@pytest.fixture
def require_app(app_available: bool) -> Generator[None, None, None]:
    """Skip test if application is not available."""
    if not app_available:
        pytest.skip("Application not available")
    yield
