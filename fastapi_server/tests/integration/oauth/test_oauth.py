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
Integration tests for OAuth authentication flow using mock OAuth2 server.

These tests verify OAuth2 flows against a Navikit mock OAuth2 server running
in a Docker container. This allows testing without connecting to real OAuth
providers.

Test categories:
- OAuth flow tests: Verify authorization URL generation and callback handling
- Error handling tests: Verify proper error responses for invalid inputs
- Security tests: Verify CSRF protection (state parameter validation)
"""

from urllib.parse import parse_qs, urlparse

import pytest
import requests


class TestOAuthFlow:
    """Test OAuth2 authentication flow with mock server."""

    @pytest.fixture
    def oauth_api_url(self, app_url: str) -> str:
        """OAuth API endpoint URL."""
        return f"{app_url}/api/v1/oauth"

    def test_list_oauth_providers(self, oauth_api_url: str, require_app: None) -> None:
        """Test listing available OAuth providers."""
        response = requests.get(f"{oauth_api_url}/", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        providers = data["providers"]

        # Verify we have at least one provider configured
        assert len(providers) > 0

        # Check provider structure
        provider = providers[0]
        assert "id" in provider
        assert "type" in provider
        assert "name" in provider

    def test_get_authorization_url(self, oauth_api_url: str, require_app: None) -> None:
        """Test getting OAuth authorization URL."""
        response = requests.post(
            f"{oauth_api_url}/authorize/", params={"provider_id": "google"}, timeout=10
        )
        assert response.status_code == 200

        data = response.json()
        assert "redirect_url" in data

        # Verify redirect URL points to authorization endpoint
        redirect_url = data["redirect_url"]
        assert "authorize" in redirect_url or "auth" in redirect_url

    def test_oauth_callback_missing_params(
        self, oauth_api_url: str, require_app: None
    ) -> None:
        """Test OAuth callback with missing parameters returns error."""
        response = requests.post(f"{oauth_api_url}/callback/", timeout=10)
        assert response.status_code == 400

    def test_oauth_callback_with_error(
        self, oauth_api_url: str, require_app: None
    ) -> None:
        """Test OAuth callback with error parameter."""
        response = requests.post(
            f"{oauth_api_url}/callback/",
            params={
                "error": "access_denied",
                "error_description": "User cancelled authorization",
            },
            timeout=10,
        )
        assert response.status_code == 400

    def test_google_oauth_happy_path(
        self, oauth_api_url: str, mock_oauth_url: str, require_app: None
    ) -> None:
        """Test complete Google OAuth flow with token exchange.

        This test verifies the happy path:
        1. Get authorization URL from the app
        2. Simulate user authorization via mock OAuth server (non-interactive mode)
        3. Complete the callback with authorization code
        4. Verify user is authenticated with proper user data

        Uses the navikt mock-oauth2-server in non-interactive mode (CI mode).
        The mock server automatically redirects with an authorization code.
        """
        # Use a session to maintain cookies across requests
        session = requests.Session()

        # Step 1: Get authorization URL from our app
        auth_response = session.post(
            f"{oauth_api_url}/authorize/", params={"provider_id": "google"}, timeout=10
        )
        assert auth_response.status_code == 200

        auth_data = auth_response.json()
        redirect_url = auth_data["redirect_url"]

        # Extract state and other params from the authorization URL
        auth_params = self._extract_query_params(redirect_url)
        state = auth_params.get("state")
        assert state is not None, (
            "State parameter should be present in authorization URL"
        )

        # Step 2: Get authorization code from mock OAuth server (non-interactive mode)
        # The mock server will auto-redirect with a code when interactiveLogin=false
        mock_authorize_response = session.get(
            f"{mock_oauth_url}/google/authorize",
            params={
                "response_type": "code",
                "client_id": auth_params.get("client_id", "test"),
                "redirect_uri": auth_params.get("redirect_uri"),
                "scope": auth_params.get("scope", "openid"),
                "state": state,
                "nonce": auth_params.get("nonce"),
            },
            allow_redirects=False,
            timeout=10,
        )

        # In non-interactive mode, the mock server redirects with the code
        assert mock_authorize_response.status_code == 302, (
            f"Expected redirect (302) from mock server but got {mock_authorize_response.status_code}. "
            "Make sure the mock server is running with interactiveLogin=false"
        )

        # Extract code from redirect location
        code = self._extract_code_from_redirect(mock_authorize_response)
        assert code is not None, (
            f"Failed to get authorization code from mock server redirect. "
            f"Location header: {mock_authorize_response.headers.get('Location', '')}"
        )

        # Step 3: Call the callback endpoint with code and state
        callback_response = session.post(
            f"{oauth_api_url}/callback/",
            params={
                "code": code,
                "state": state,
            },
            timeout=10,
        )

        # Step 4: Verify the response
        # The callback should return user data on success
        assert callback_response.status_code == 200, (
            f"Expected 200 OK but got {callback_response.status_code}. "
            f"Response: {callback_response.text}"
        )

        user_data = callback_response.json()

        # Verify user data structure
        assert "uuid" in user_data
        assert "email" in user_data
        assert "identities" in user_data

        # Verify the user has at least one identity (from Google OAuth)
        identities = user_data["identities"]
        assert len(identities) > 0

        # Verify the identity is from Google
        google_identity = next(
            (i for i in identities if i.get("provider_type") == "google"), None
        )
        assert google_identity is not None, "Should have a Google identity"
        assert google_identity["provider_id"] == "google"

    def test_microsoft_oauth_happy_path(
        self, oauth_api_url: str, mock_oauth_url: str, require_app: None
    ) -> None:
        """Test complete Microsoft OAuth flow with token exchange.

        This test verifies the happy path for Microsoft OIDC:
        1. Get authorization URL from the app
        2. Simulate user authorization via mock OAuth server (non-interactive mode)
        3. Complete the callback with authorization code
        4. Verify user is authenticated with proper user data

        This validates that the OIDC discovery flow (server_metadata_url) works
        correctly with the openid scope, producing a valid id_token that maps
        to the expected Profile format (sub, email, name).
        """
        session = requests.Session()

        # Step 1: Get authorization URL from our app
        auth_response = session.post(
            f"{oauth_api_url}/authorize/",
            params={"provider_id": "microsoft"},
            timeout=10,
        )
        assert auth_response.status_code == 200

        auth_data = auth_response.json()
        redirect_url = auth_data["redirect_url"]

        # Extract state and other params from the authorization URL
        auth_params = self._extract_query_params(redirect_url)
        state = auth_params.get("state")
        assert state is not None, (
            "State parameter should be present in authorization URL"
        )

        # Verify openid scope is included (required for OIDC id_token flow)
        scope = auth_params.get("scope", "")
        assert "openid" in scope, (
            f"openid scope must be present for Microsoft OIDC flow, got: {scope}"
        )

        # Step 2: Get authorization code from mock OAuth server (non-interactive mode)
        mock_authorize_response = session.get(
            f"{mock_oauth_url}/microsoft/authorize",
            params={
                "response_type": "code",
                "client_id": auth_params.get("client_id", "test"),
                "redirect_uri": auth_params.get("redirect_uri"),
                "scope": auth_params.get("scope", "openid"),
                "state": state,
                "nonce": auth_params.get("nonce"),
            },
            allow_redirects=False,
            timeout=10,
        )

        assert mock_authorize_response.status_code == 302, (
            f"Expected redirect (302) from mock server but got {mock_authorize_response.status_code}. "
            "Make sure the mock server is running with interactiveLogin=false"
        )

        # Extract code from redirect location
        code = self._extract_code_from_redirect(mock_authorize_response)
        assert code is not None, (
            f"Failed to get authorization code from mock server redirect. "
            f"Location header: {mock_authorize_response.headers.get('Location', '')}"
        )

        # Step 3: Call the callback endpoint with code and state
        callback_response = session.post(
            f"{oauth_api_url}/callback/",
            params={
                "code": code,
                "state": state,
            },
            timeout=10,
        )

        # Step 4: Verify the response
        assert callback_response.status_code == 200, (
            f"Expected 200 OK but got {callback_response.status_code}. "
            f"Response: {callback_response.text}"
        )

        user_data = callback_response.json()

        # Verify user data structure
        assert "uuid" in user_data
        assert "email" in user_data
        assert "identities" in user_data

        # Verify the user has at least one identity (from Microsoft OAuth)
        identities = user_data["identities"]
        assert len(identities) > 0

        # Verify the identity is from Microsoft
        microsoft_identity = next(
            (i for i in identities if i.get("provider_type") == "microsoft"), None
        )
        assert microsoft_identity is not None, "Should have a Microsoft identity"
        assert microsoft_identity["provider_id"] == "microsoft"

    def _extract_query_params(self, url: str) -> dict[str, str]:
        """Extract query parameters from URL as a flat dictionary."""
        query_params = parse_qs(urlparse(url).query)
        return {k: v[0] for k, v in query_params.items()}

    def _extract_code_from_redirect(self, response: requests.Response) -> str | None:
        """Extract authorization code from redirect response Location header."""
        location = response.headers.get("Location", "")
        params = parse_qs(urlparse(location).query)
        codes = params.get("code", [None])
        return codes[0] if codes else None


class TestOAuthErrorHandling:
    """Test OAuth error handling scenarios."""

    @pytest.fixture
    def oauth_api_url(self, app_url: str) -> str:
        """OAuth API endpoint URL."""
        return f"{app_url}/api/v1/oauth"

    def test_invalid_provider_id(self, oauth_api_url: str, require_app: None) -> None:
        """Test authorization with invalid provider ID."""
        response = requests.post(
            f"{oauth_api_url}/authorize/",
            params={"provider_id": "invalid-provider"},
            timeout=10,
        )
        # Should return error (400 or 404)
        assert response.status_code in [400, 404]

    def test_callback_invalid_state(
        self, oauth_api_url: str, require_app: None
    ) -> None:
        """Test callback with invalid state parameter."""
        response = requests.post(
            f"{oauth_api_url}/callback/",
            params={"code": "test-code", "state": "invalid-state-token"},
            timeout=10,
        )
        assert response.status_code == 400

    def test_callback_without_state(
        self, oauth_api_url: str, require_app: None
    ) -> None:
        """Test callback without state parameter (CSRF protection)."""
        response = requests.post(
            f"{oauth_api_url}/callback/", params={"code": "test-code"}, timeout=10
        )
        assert response.status_code == 400


class TestOAuthSecurity:
    """Test OAuth security features."""

    @pytest.fixture
    def oauth_api_url(self, app_url: str) -> str:
        """OAuth API endpoint URL."""
        return f"{app_url}/api/v1/oauth"

    def test_state_parameter_required(
        self, oauth_api_url: str, require_app: None
    ) -> None:
        """Verify state parameter is required for CSRF protection."""
        response = requests.post(
            f"{oauth_api_url}/callback/", params={"code": "test-code"}, timeout=10
        )
        assert response.status_code == 400


class TestMockOAuthServer:
    """Test mock OAuth2 server endpoints directly.

    These tests verify the mock server is properly configured and responding
    as expected for different OAuth providers.
    """

    def test_google_openid_configuration(self, mock_oauth_url: str) -> None:
        """Test Google OpenID configuration endpoint."""
        response = requests.get(
            f"{mock_oauth_url}/google/.well-known/openid-configuration", timeout=5
        )
        assert response.status_code == 200

        config = response.json()
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config
        assert "issuer" in config

    def test_box_openid_configuration(self, mock_oauth_url: str) -> None:
        """Test Box OpenID configuration endpoint."""
        response = requests.get(
            f"{mock_oauth_url}/box/.well-known/openid-configuration", timeout=5
        )
        assert response.status_code == 200

        config = response.json()
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config

    def test_microsoft_openid_configuration(self, mock_oauth_url: str) -> None:
        """Test Microsoft OpenID configuration endpoint."""
        response = requests.get(
            f"{mock_oauth_url}/microsoft/.well-known/openid-configuration", timeout=5
        )
        assert response.status_code == 200

        config = response.json()
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config
