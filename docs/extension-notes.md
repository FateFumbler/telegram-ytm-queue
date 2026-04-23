# Extension Notes

The MV3 extension is the Phase 3 path for browser-native queue control.

## Current behavior
- polls the backend for ready jobs
- sends job payload to a content script on `music.youtube.com`
- executes real DOM actions for `Play next`, `Add to queue`, and `Skip`
- reports success/failure plus current now-playing state via the backend

## Live-validation step
The content script now contains real DOM selectors for:
- opening search
- targeting the resolved track
- invoking `Play next` or `Add to queue`
- clicking the player `Next` control for `/skip`

This keeps browser control inside the active YT Music tab instead of relying only on Playwright.
