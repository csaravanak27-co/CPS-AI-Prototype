# C.P.S. Browser Extension — Official Store Listing Placeholder

**Publication status:** Not published. This document is submission-ready copy
for the publisher to review and paste into an official Chrome Web Store or
Microsoft Edge Add-ons listing. No listing URL is assigned yet.

## Listing metadata

- **Name:** C.P.S. — AI Coding Companion
- **Short description:** User-controlled AI coding help with a local-first backend and offline mode.
- **Category:** Developer Tools
- **Version:** Read from `extension/manifest.json` at release time.
- **Publisher:** C.P.S. Team (replace with the publisher's legal name before submission)
- **Official listing URL:** Leave blank until the store publishes the listing.

## Long description

C.P.S. is a browser-based coding companion for explaining, generating,
debugging, optimizing, converting, testing, and security-reviewing code.

Use the side panel for chat and Code Studio, or select text and choose a C.P.S.
action from the context menu. Requests try the local C.P.S. backend first. The
built-in offline provider works without an account, download, or API key. If a
user chooses a hosted provider, they enter and control their own optional API
key in the extension settings.

The extension does not require a C.P.S. account. It stores settings and
conversation history in browser-local storage. It does not include remote code,
advertising, analytics, or background telemetry.

## Permission disclosure

| Permission | User-facing purpose |
|---|---|
| `activeTab` | Read a selection after the user invokes C.P.S. |
| `storage` | Keep settings and conversation history on the device. |
| `sidePanel` | Show the persistent assistant panel. |
| `contextMenus` | Provide C.P.S. actions for selected text. |
| `scripting` | Add the selection helper after an explicit user action on an unsupported page. |
| Localhost host access | Connect to the optional local backend at the configured default. |
| Optional provider origins | Contact only the hosted provider selected by the user. |

## Data-use disclosure

- **Data sold:** None.
- **Advertising:** None.
- **Authentication:** No C.P.S. account or sign-in is required.
- **Remote code:** None.
- **Prompts and selections:** Sent only to the local backend or provider selected by the user.
- **API keys:** Optional, entered by the user, kept in browser-local storage, and used only for direct provider requests.
- **History:** Stored locally until the user clears it.
- **Support contact:** Add the publisher-maintained support contact before submission.

The authoritative privacy wording is in `docs/PRIVACY.md`. Review it against
the store's current disclosure form immediately before submission.

## Store assets to provide

- 16px, 32px, 48px, and 128px icons from `extension/icons/`.
- A sidebar screenshot showing Chat and Settings.
- A context-menu or selection-helper screenshot.
- A short screen recording, if requested by the store review form.

Do not describe the extension as published, approved, or available from an
official store until the publisher completes review and records the resulting
listing identifier.
