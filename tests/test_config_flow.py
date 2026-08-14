"""Config-flow error paths. All xAI calls are mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.grok_oauth.const import (
    CONF_SELECTED_MODELS,
    DOMAIN,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
)
from custom_components.grok_oauth.oauth import GrokOAuthError, OAuthTokens

MOCK_TOKENS = OAuthTokens(
    access_token="test-access-token",
    refresh_token="test-refresh-token",
    expires_at=9999999999,
)
MOCK_ACCOUNT = {
    "sub": "acct-1",
    "email": "grok@example.com",
    "name": "Grok User",
}


async def _start_browser(hass: HomeAssistant) -> tuple[str, dict]:
    """Open the user step and continue into browser paste-callback."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"]["redirect_uri"] == OAUTH_REDIRECT_URI

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"method": "browser"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "browser"
    placeholders = result["description_placeholders"]
    assert placeholders["redirect_uri"] == OAUTH_REDIRECT_URI
    authorize = placeholders["authorize_url"]
    params = parse_qs(urlparse(authorize).query)
    assert params["client_id"] == [OAUTH_CLIENT_ID]
    assert params["redirect_uri"] == [OAUTH_REDIRECT_URI]
    assert "my.home-assistant.io" not in authorize
    return result["flow_id"], placeholders


async def test_user_step_shows_sign_in_methods(hass: HomeAssistant) -> None:
    """The first step is method selection, not My Home Assistant OAuth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] in (None, {})


async def test_browser_missing_code(hass: HomeAssistant) -> None:
    """Empty paste and a callback without code= are missing_code."""
    flow_id, _placeholders = await _start_browser(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {"callback_url": ""}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "missing_code"

    result = await hass.config_entries.flow.async_configure(
        flow_id, {"callback_url": "http://127.0.0.1:56121/callback"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "missing_code"


async def test_browser_state_mismatch(hass: HomeAssistant) -> None:
    """A callback whose state does not match this attempt is rejected."""
    flow_id, placeholders = await _start_browser(hass)
    expected_state = parse_qs(urlparse(placeholders["authorize_url"]).query)["state"][0]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "callback_url": (
                f"http://127.0.0.1:56121/callback?code=abc&state=not-{expected_state}"
            )
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "state_mismatch"


async def test_browser_access_denied(hass: HomeAssistant) -> None:
    """xAI access_denied on the callback aborts setup."""
    flow_id, _placeholders = await _start_browser(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"callback_url": "http://127.0.0.1:56121/callback?error=access_denied"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "access_denied"


async def test_browser_oauth_error_on_callback(hass: HomeAssistant) -> None:
    """Other callback error codes surface as oauth_failed."""
    flow_id, _placeholders = await _start_browser(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"callback_url": "http://127.0.0.1:56121/callback?error=server_error"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "oauth_failed"


async def test_browser_exchange_cannot_connect(hass: HomeAssistant) -> None:
    """A mocked token-exchange transport failure stays on the form."""
    flow_id, _placeholders = await _start_browser(hass)
    with patch(
        "custom_components.grok_oauth.config_flow.exchange_authorization_code",
        new=AsyncMock(side_effect=GrokOAuthError("cannot_connect", "down")),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"callback_url": "bare-auth-code"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_browser_exchange_oauth_failed(hass: HomeAssistant) -> None:
    """A mocked token-exchange OAuth failure stays on the form."""
    flow_id, _placeholders = await _start_browser(hass)
    with patch(
        "custom_components.grok_oauth.config_flow.exchange_authorization_code",
        new=AsyncMock(side_effect=GrokOAuthError("oauth_failed", "bad code")),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"callback_url": "bare-auth-code"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "oauth_failed"


async def test_browser_exchange_tier_blocked(hass: HomeAssistant) -> None:
    """A mocked 403 / tier block aborts setup."""
    flow_id, _placeholders = await _start_browser(hass)
    with patch(
        "custom_components.grok_oauth.config_flow.exchange_authorization_code",
        new=AsyncMock(side_effect=GrokOAuthError("tier_blocked", "not entitled")),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"callback_url": "bare-auth-code"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "tier_blocked"


async def test_device_cannot_connect(hass: HomeAssistant) -> None:
    """Device-code start failure aborts without talking to xAI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "custom_components.grok_oauth.config_flow.request_device_authorization",
        new=AsyncMock(side_effect=GrokOAuthError("cannot_connect", "down")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"method": "device"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_models_requires_selection(hass: HomeAssistant) -> None:
    """The model picker rejects an empty multi-select."""
    flow_id, _placeholders = await _start_browser(hass)
    with (
        patch(
            "custom_components.grok_oauth.config_flow.exchange_authorization_code",
            new=AsyncMock(return_value=MOCK_TOKENS),
        ),
        patch(
            "custom_components.grok_oauth.config_flow.fetch_userinfo",
            new=AsyncMock(return_value=MOCK_ACCOUNT),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"callback_url": "bare-auth-code"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "models"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SELECTED_MODELS: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "select_model"


async def test_browser_success_creates_entry(hass: HomeAssistant) -> None:
    """A mocked successful paste-callback creates the config entry."""
    flow_id, _placeholders = await _start_browser(hass)
    with (
        patch(
            "custom_components.grok_oauth.config_flow.exchange_authorization_code",
            new=AsyncMock(return_value=MOCK_TOKENS),
        ),
        patch(
            "custom_components.grok_oauth.config_flow.fetch_userinfo",
            new=AsyncMock(return_value=MOCK_ACCOUNT),
        ),
        patch(
            "custom_components.grok_oauth.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"callback_url": "bare-auth-code"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "models"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SELECTED_MODELS: ["grok-4.6", "voice"]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["access_token"] == "test-access-token"
    assert result["data"][CONF_SELECTED_MODELS] == ["grok-4.6", "voice"]
    assert result["result"].unique_id == "acct-1"
