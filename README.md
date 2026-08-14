# Grok OAuth for Home Assistant

Unofficial custom integration that signs in with a **SuperGrok** / **X Premium+** account (no `XAI_API_KEY`) and exposes Grok to Home Assistant.

> This uses xAI’s SuperGrok OAuth surface (the same family of flow as Grok CLI / Hermes). It is unofficial. xAI can change or gate it at any time.

## What it exposes

After you pick models in the multi-picker:

| Picker option | Home Assistant surface |
| --- | --- |
| Chat models (`grok-4.6`, …) | Conversation agents + AI Task |
| **Voice** | TTS (`POST /v1/tts`) and STT (`POST /v1/stt`) |
| **Realtime** | Conversation agent over `wss://api.x.ai/v1/realtime` (falls back to chat if the socket fails) |
| Imagine | `ai_task.generate_image` + `grok_oauth.generate_image` |

## Install with HACS

1. HACS → Integrations → ⋮ → **Custom repositories**
2. URL: `https://github.com/helv-io/ha-grok-oauth`
3. Category: **Integration**
4. Download **Grok OAuth**
5. Restart Home Assistant
6. **Settings → Devices & services → Add integration → Grok OAuth**

## Setup

xAI’s SuperGrok / Grok CLI public client only allows `http://127.0.0.1:56121/callback`. It rejects My Home Assistant (`https://my.home-assistant.io/redirect/oauth`).

**Browser login**

1. Choose **Browser login (paste the localhost callback URL)**.
2. Open the SuperGrok sign-in link and approve access.
3. The browser then goes to `http://127.0.0.1:56121/callback?...` and fails to connect. That is expected — nothing is listening on your computer.
4. Copy the **full URL** from the address bar (it contains `code=`) and paste it back into the setup form.

**Device code** (no paste): open the verification URL on any device and approve. The form continues automatically.

Then multi-select chat models, Voice, Realtime, and Imagine, and point your Voice Assistant pipeline at **Grok Voice STT** → a Grok conversation agent → **Grok Voice TTS**.

## Services

- `grok_oauth.generate_content`
- `grok_oauth.generate_image`
- `grok_oauth.create_realtime_session`

## Logging

One-line info logs for conversation, chat, STT, TTS, Imagine, and token refresh. Secrets are never logged.

For request traces: **Settings → System → Logs →** set `custom_components.grok_oauth` to **debug**.

Diagnostics (three-dot menu on the integration card) include selected models, token expiry, and recent events — no tokens.

## Requirements

- Home Assistant 2026.8+
- SuperGrok or X Premium+
