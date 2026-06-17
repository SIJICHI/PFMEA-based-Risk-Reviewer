# OAuth Integration Tests

Integration tests for OAuth authentication flows using a [Navikit mock OAuth2 server](https://github.com/navikt/mock-oauth2-server).

## Overview

These tests verify OAuth2 functionality without connecting to real OAuth providers.
The tests run against a mock OAuth2 server deployed in a Docker container.

## Quick Start

### Start the App

To run the full OAuth flow tests (including token exchange), the FastAPI app must be
configured to use the mock OAuth server instead of real OAuth providers.

#### Configuration for Mock Server

Set these environment variables when starting the app:

```bash
# Point Google OAuth to mock server
export GOOGLE_SERVER_METADATA_URL=http://localhost:18881/google/.well-known/openid-configuration

# Use test credentials (any values work with mock server)
export GOOGLE_CLIENT_ID=test-client-id
export GOOGLE_CLIENT_SECRET=test-client-secret

# Point Microsoft OAuth to mock server
export MICROSOFT_SERVER_METADATA_URL=http://localhost:18881/microsoft/.well-known/openid-configuration
# Use test credentials (any values work with mock server)
export MICROSOFT_CLIENT_ID=test-client-id
export MICROSOFT_CLIENT_SECRET=test-client-secret

export OAUTH_IMPL=authlib
# Allow cookies over HTTP (required for local testing)
export SESSION_HTTPS_ONLY=false

# Start the app with the mock server configuration
task dev
```


### Run the OAuth Integration Tests

When the app is running, open a new terminal session and run the tests:

```bash
# from the root of the project
task fastapi_server:test-oauth
```

This command will:
1. Start the mock OAuth2 server
2. Wait for the server to be ready
3. Run the OAuth integration tests
4. Stop and clean up the app and mock server


### Supported OAuth Providers

The mock server supports the following issuers:
- `google` - Google OAuth2
- `box` - Box OAuth2
- `microsoft` - Microsoft OAuth2

Each issuer is available at `http://localhost:18881/{issuer}/`.

## Notes

- Tests that require the application to be running will be skipped if the app is not available
- The mock server starts on port 18881 to avoid conflicts with other services
- Tests are automatically skipped if the mock OAuth server is not running
