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
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.auth.api_key import APIKeyValidator, DataRobotAPIKeyHeader, DRUser


@pytest.fixture
def mock_request() -> MagicMock:
    """Fixture for a mock request object."""
    request = MagicMock()
    request.headers = {}
    return request


@pytest.fixture
def mock_api_key_validator() -> Generator[AsyncMock, None, None]:
    """Fixture for patching APIKeyValidator.validate."""
    with patch.object(
        APIKeyValidator, "validate", new_callable=AsyncMock
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def dr_user() -> Mock:
    """Fixture for a sample DataRobotUser."""
    return Mock(
        spec=DRUser,
        id="user_id",
        email="test@datarobot.com",
        org_id="org_id",
        permissions={},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth_scheme",
    ["Bearer", "bearer", "BEARER"],
    ids=["standard", "lowercase", "uppercase"],
)
async def test_datarobot_api_key_header_bearer(
    mock_request: MagicMock,
    mock_api_key_validator: AsyncMock,
    dr_user: Mock,
    auth_scheme: str,
) -> None:
    """Test authentication with Bearer token (RFC 6750 case-insensitive compliance)."""
    api_key = "test-api-key"
    mock_request.headers["Authorization"] = f"{auth_scheme} {api_key}"
    mock_api_key_validator.return_value = dr_user

    security_scheme = DataRobotAPIKeyHeader()
    credentials = await security_scheme(mock_request)

    assert credentials is not None
    assert credentials.scheme == "Bearer"
    assert credentials.credentials == api_key


@pytest.mark.asyncio
async def test_datarobot_api_key_header_x_datarobot_api_key(
    mock_request: MagicMock, mock_api_key_validator: AsyncMock, dr_user: Mock
) -> None:
    """Test authentication with x-datarobot-api-key header."""
    api_key = "test-api-key"
    mock_request.headers["x-datarobot-api-key"] = api_key
    mock_api_key_validator.return_value = dr_user

    security_scheme = DataRobotAPIKeyHeader()
    credentials = await security_scheme(mock_request)

    assert credentials is not None
    assert credentials.scheme == "ApiKey"
    assert credentials.credentials == api_key
