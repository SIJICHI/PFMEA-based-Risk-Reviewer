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
import os
from dataclasses import dataclass
from typing import Final

import pulumi
import pulumi_datarobot as datarobot
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME

OAUTH_IMPL: Final[str] = "OAUTH_IMPL"

app_runtime_parameters = [
    datarobot.ApplicationSourceRuntimeParameterValueArgs(
        type="string",
        key=OAUTH_IMPL,
        value="authlib",
    )
]


@dataclass(frozen=True)
class ProviderConfig:
    """OAuth provider configuration."""

    name: str
    client_id_key: str
    client_secret_key: str


AUTHLIB_OAUTH_PROVIDERS = [
    ProviderConfig(
        name="Google",
        client_id_key="GOOGLE_CLIENT_ID",
        client_secret_key="GOOGLE_CLIENT_SECRET",
    ),
    ProviderConfig(
        name="Box",
        client_id_key="BOX_CLIENT_ID",
        client_secret_key="BOX_CLIENT_SECRET",
    ),
    ProviderConfig(
        name="Microsoft",
        client_id_key="MICROSOFT_CLIENT_ID",
        client_secret_key="MICROSOFT_CLIENT_SECRET",
    ),
]


def add_oauth_provider(provider: ProviderConfig, parameters: list) -> None:
    client_id = os.environ.get(provider.client_id_key)
    client_secret = os.environ.get(provider.client_secret_key)

    if client_id and client_secret:
        pulumi.info(
            f"{provider.name} OAuth credentials found, adding to application runtime parameters."
        )
        pulumi.export(f"{provider.name} Client ID", client_id)

        client_secret_cred = datarobot.ApiTokenCredential(
            f"[{PROJECT_NAME}] Agentic Starter {provider.name} Client",
            args=datarobot.ApiTokenCredentialArgs(
                api_token=str(client_secret),
            ),
        )

        parameters.extend(
            [
                datarobot.ApplicationSourceRuntimeParameterValueArgs(
                    type="string",
                    key=provider.client_id_key,
                    value=client_id,
                ),
                datarobot.ApplicationSourceRuntimeParameterValueArgs(
                    type="credential",
                    key=provider.client_secret_key,
                    value=client_secret_cred.id,
                ),
            ]
        )


for provider in AUTHLIB_OAUTH_PROVIDERS:
    add_oauth_provider(provider, app_runtime_parameters)
