# Obscura benchmark and fit assessment

Date: 2026-04-23
Project: `telegram-ytm-queue`

## Goal
Evaluate whether Obscura can help complete the Telegram group driven YouTube Music queue system.

## Test setup
- Obscura release: `v0.1.0`
- Platform: Ubuntu host used by Hermes
- Comparison target: Playwright with bundled Chromium
- Repetitions: 3 per case

## Cases
1. `example_title`
   - URL: `https://example.com`
   - Check: page title extraction
2. `quotes_count`
   - URL: `https://quotes.toscrape.com/js/`
   - Check: JS-rendered quote count

## Results

| Tool | Case | Avg time | Min time | Avg RSS | Output |
|---|---:|---:|---:|---:|---|
| Obscura | example_title | 1.530s | 0.620s | 31,565 KB | `Example Domain` |
| Playwright Chromium | example_title | 1.820s | 1.520s | 96,176 KB | `Example Domain` |
| Obscura | quotes_count | 4.167s | 3.420s | 43,769 KB | `10.0` |
| Playwright Chromium | quotes_count | 3.067s | 2.860s | 102,037 KB | `10` |

## Observations
- Obscura used much less memory in both cases.
- On the trivial page, Obscura was slightly faster.
- On the JS-rendered page, Playwright Chromium was faster.
- Obscura is promising as a lightweight automation runtime, but not yet a clear universal speed win.

## Fit for `telegram-ytm-queue`
### Where Obscura could help
- Replace or supplement the not-yet-wired Playwright local worker path.
- Reduce memory footprint for a dedicated local automation lane.
- Potentially simplify a single-purpose browser worker that owns the YouTube Music session.

### Where Obscura does not solve the main product problem
- The real product requirement is controlling the **active current YouTube Music queue**.
- The most reliable architecture for that remains the browser-native extension path attached to the real `music.youtube.com` tab.
- Obscura does not remove the need for site-specific DOM interaction and queue-action wiring.
- If the user wants queue control on the exact live browser tab already playing music, the MV3 extension remains the stronger architecture.

## Project status cross-check
- Tests currently pass: `8 passed`
- `extension/content.js` contains real DOM automation for:
  - search navigation
  - result ranking
  - action menu open
  - `Play next`
  - `Add to queue`
- `app/playwright_controller.py` is still a stub and is not the primary completion path.

## Recommendation
- Do **not** pivot this project to Obscura as the main completion strategy.
- Keep the extension as the primary execution path for the current queue problem.
- Consider Obscura only as an optional future worker lane if we want a lighter non-extension automation backend.
