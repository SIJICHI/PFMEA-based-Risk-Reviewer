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
import logging
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING

from datarobot.auth.authlib.oauth import AsyncOAuth as AuthlibOAuth
from datarobot.auth.authlib.oauth import OAuthProviderConfig
from datarobot.auth.datarobot.oauth import AsyncOAuth as DatarobotOAuth
from datarobot.auth.oauth import AsyncOAuthComponent
from pydantic_settings import BaseSettings

from app.users.auth import box_user_info_mapper
from app.users.identity import ProviderType

if TYPE_CHECKING:
    from app import Config

logger = logging.getLogger(__name__)


class OAuthImpl(str, Enum):
    """
    OAuth implementations supported by the application template.
    """

    AUTHLIB = "authlib"
    DATAROBOT = "datarobot"

    @classmethod
    def all(cls) -> list[str]:
        """
        Returns a list of all available OAuth implementations.
        """
        return [impl.value for impl in OAuthImpl]


class OAuthServerURLs(BaseSettings):
    """
    OAuth server URLs configuration.

    The default values are set to the well-known endpoints for Google and Microsoft,
    and the standard endpoints for Box. Config is used to allow overriding these values
    for better testability and flexibility, but in most cases, the defaults should work without
    modification.
    """

    # Google
    google_server_metadata_url: str = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    # Box
    box_authorize_url: str = "https://account.box.com/api/oauth2/authorize"
    box_access_token_url: str = "https://api.box.com/oauth2/token"
    box_userinfo_endpoint: str = "https://api.box.com/2.0/users/me"

    # Microsoft
    microsoft_server_metadata_url: str = (
        "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
    )


@lru_cache
def get_oauth_server_urls() -> OAuthServerURLs:
    """Get cached OAuth server URLs configuration."""
    return OAuthServerURLs()


def get_oauth(config: "Config") -> AsyncOAuthComponent:
    if config.oauth_impl == OAuthImpl.DATAROBOT:
        if not config.datarobot_oauth_providers:
            logger.warning(
                "No OAuth providers configured for the DataRobot implementation. "
                "Use the `DATAROBOT_OAUTH_PROVIDERS` environment variable to set them up."
            )

        return DatarobotOAuth(
            config.datarobot_oauth_providers,
            datarobot_endpoint=config.datarobot_endpoint,
            datarobot_api_token=config.datarobot_api_token,
        )

    if config.oauth_impl == OAuthImpl.AUTHLIB:
        provider_configs: list[OAuthProviderConfig] = []
        urls = get_oauth_server_urls()

        if config.google_client_id and config.google_client_secret:
            provider_configs.append(
                OAuthProviderConfig(
                    id=ProviderType.GOOGLE.value,
                    client_id=config.google_client_id,
                    client_secret=config.google_client_secret,
                    scope="openid email profile https://www.googleapis.com/auth/drive.readonly",
                    server_metadata_url=urls.google_server_metadata_url,
                    authorize_params={
                        "access_type": "offline",
                        "prompt": "consent",  # TODO: can we remove the prompt param here?
                    },
                )
            )

        if config.box_client_id and config.box_client_secret:
            provider_configs.append(
                OAuthProviderConfig(
                    id=ProviderType.BOX.value,
                    client_id=config.box_client_id,
                    client_secret=config.box_client_secret,
                    scope="root_readwrite",
                    authorize_url=urls.box_authorize_url,
                    access_token_url=urls.box_access_token_url,
                    userinfo_endpoint=urls.box_userinfo_endpoint,
                    userinfo_mapper=box_user_info_mapper,
                )
            )

        if config.microsoft_client_id and config.microsoft_client_secret:
            provider_configs.append(
                OAuthProviderConfig(
                    id=ProviderType.MICROSOFT.value,
                    client_id=config.microsoft_client_id,
                    client_secret=config.microsoft_client_secret,
                    scope="openid email profile https://graph.microsoft.com/Files.ReadWrite.All offline_access",
                    server_metadata_url=urls.microsoft_server_metadata_url,
                )
            )

        if not provider_configs:
            logger.warning(
                "No OAuth providers configured for the authlib implementation. "
                "Use the `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, "
                "`MICROSOFT_CLIENT_ID`, and `MICROSOFT_CLIENT_SECRET` environment variables to set them up."
            )

        return AuthlibOAuth(provider_config=provider_configs)

    raise ValueError(
        f"Unsupported OAuth implementation: {config.oauth_impl}. "
        f"Available implementations: {', '.join(OAuthImpl.all())}."
    )
