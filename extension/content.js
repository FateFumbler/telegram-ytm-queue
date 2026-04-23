const SEARCH_URL = 'https://music.youtube.com/search?q=';
const RESULT_ROW_SELECTOR = 'ytmusic-responsive-list-item-renderer';
const MENU_ITEM_SELECTOR = 'ytmusic-menu-service-item-renderer, ytmusic-toggle-menu-service-item-renderer';
const ACTION_MENU_SELECTOR = 'button[aria-label*="Action menu"], tp-yt-paper-icon-button[aria-label*="Action menu"], #menu tp-yt-paper-icon-button';
const PLAYER_TITLE_SELECTORS = [
  'ytmusic-player-bar .title',
  'ytmusic-player-bar .content-info-wrapper .title',
  'ytmusic-player-bar .song-title',
];
const PLAYER_SUBTITLE_SELECTORS = [
  'ytmusic-player-bar .byline',
  'ytmusic-player-bar .subtitle',
  'ytmusic-player-bar .content-info-wrapper .byline',
];
const NEXT_BUTTON_SELECTORS = [
  'ytmusic-player-bar .next-button button',
  'ytmusic-player-bar tp-yt-paper-icon-button.next-button',
  'ytmusic-player-bar [aria-label="Next"]',
  'ytmusic-player-bar [aria-label*="Next"]',
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalize(text) {
  return (text || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function extractText(root, selectorList) {
  for (const selector of selectorList) {
    const node = root.querySelector(selector);
    if (node?.textContent?.trim()) return node.textContent.trim();
  }
  return '';
}

async function waitFor(predicate, timeout = 12000, interval = 200) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const result = predicate();
    if (result) return result;
    await sleep(interval);
  }
  return null;
}

function candidateNeedle(job) {
  const candidate = job.candidate || {};
  return {
    title: normalize(candidate.title || job.query || ''),
    artist: normalize(candidate.artist || ''),
    query: normalize(job.query || ''),
  };
}

function scoreRow(row, needle) {
  const text = normalize(row.innerText || row.textContent || '');
  let score = 0;
  if (needle.title && text.includes(needle.title)) score += 5;
  if (needle.artist && text.includes(needle.artist)) score += 3;
  if (needle.query && text.includes(needle.query)) score += 2;
  if (text.includes('song')) score += 1;
  return score;
}

async function navigateToSearch(job) {
  const url = `${SEARCH_URL}${encodeURIComponent(job.query || job.candidate?.title || '')}`;
  if (location.href !== url) {
    location.href = url;
  }
  await waitFor(() => document.querySelector(RESULT_ROW_SELECTOR), 15000, 300);
  await sleep(700);
}

async function findBestRow(job) {
  const needle = candidateNeedle(job);
  return waitFor(() => {
    const rows = [...document.querySelectorAll(RESULT_ROW_SELECTOR)];
    if (!rows.length) return null;
    const ranked = rows
      .map((row) => ({ row, score: scoreRow(row, needle) }))
      .sort((a, b) => b.score - a.score);
    return ranked[0]?.score > 0 ? ranked[0].row : rows[0];
  }, 10000, 250);
}

async function clickActionMenu(row) {
  const button = row.querySelector(ACTION_MENU_SELECTOR);
  if (!button) throw new Error('Action menu button not found on result row');
  button.click();
  const menu = await waitFor(() => document.querySelector(MENU_ITEM_SELECTOR), 6000, 150);
  if (!menu) throw new Error('Queue action menu did not open');
}

async function chooseMenuAction(labelText) {
  const wanted = normalize(labelText);
  const items = [...document.querySelectorAll(MENU_ITEM_SELECTOR)];
  const match = items.find((item) => normalize(item.innerText || item.textContent || '').includes(wanted));
  if (!match) throw new Error(`Menu action not found: ${labelText}`);
  match.click();
}

function currentNowPlaying() {
  const title = extractText(document, PLAYER_TITLE_SELECTORS);
  const subtitle = extractText(document, PLAYER_SUBTITLE_SELECTORS);
  if (title && subtitle) return `${title} — ${subtitle}`;
  return title || subtitle || '';
}

async function executeQueueAction(job) {
  if (job.intent === 'skip') {
    const button = NEXT_BUTTON_SELECTORS.map((selector) => document.querySelector(selector)).find(Boolean);
    if (!button) throw new Error('Next button not found in YouTube Music player bar');
    button.click();
    await sleep(1200);
    const nowPlaying = currentNowPlaying() || null;
    return {
      ok: true,
      detail: nowPlaying ? `Skipped to: ${nowPlaying}` : 'Skipped current track',
      nowPlaying,
    };
  }
  await navigateToSearch(job);
  const row = await findBestRow(job);
  if (!row) throw new Error('Could not locate a matching YouTube Music result');
  const action = job.intent === 'play_next' ? 'Play next' : 'Add to queue';
  await clickActionMenu(row);
  await chooseMenuAction(action);
  await sleep(800);
  return {
    ok: true,
    detail: `${action}: ${job.candidate?.title || job.query}`,
    nowPlaying: currentNowPlaying() || null,
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'ytm-state') {
    sendResponse({ ok: true, nowPlaying: currentNowPlaying() || null });
    return false;
  }

  if (message.type === 'ytm-queue-job') {
    executeQueueAction(message.job)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, detail: error?.message || String(error), nowPlaying: currentNowPlaying() || null }));
    return true;
  }
});
