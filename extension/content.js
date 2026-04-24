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
const QUEUE_ITEM_SELECTORS = [
  'ytmusic-player-queue-item',
  'ytmusic-queue-item',
  'ytmusic-playlist-panel-video-renderer',
];
const PLAY_NEXT_INSERT_POSITION = 'INSERT_AFTER_CURRENT_VIDEO';
const ADD_TO_QUEUE_INSERT_POSITION = 'INSERT_AT_END';
// Play-next queueAddEndpoint sends queueInsertPosition: 'INSERT_AFTER_CURRENT_VIDEO'.

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
    const result = await predicate();
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
    videoId: candidate.video_id || candidate.videoId || job.video_id || job.videoId || '',
  };
}

function currentNowPlaying() {
  const title = extractText(document, PLAYER_TITLE_SELECTORS);
  const subtitle = extractText(document, PLAYER_SUBTITLE_SELECTORS);
  if (title && subtitle) return `${title} — ${subtitle}`;
  return title || subtitle || '';
}

function getYtmConfig() {
  if (!window.ytcfg) throw new Error('YouTube Music config is not available');
  const context = window.ytcfg.get('INNERTUBE_CONTEXT');
  const apiKey = window.ytcfg.get('INNERTUBE_API_KEY');
  if (!context || !apiKey) throw new Error('YouTube Music Innertube context is not available');
  return { context, apiKey };
}

async function innertubeFetch(path, body) {
  const { context, apiKey } = getYtmConfig();
  const client = context.client || {};
  const endpoint = `/youtubei/v1/${path}`;
  const response = await fetch(`${endpoint}?key=${apiKey}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'content-type': 'application/json',
      'x-origin': 'https://music.youtube.com',
      'x-youtube-client-name': '67',
      'x-youtube-client-version': client.clientVersion || '',
      'x-goog-authuser': '0',
    },
    body: JSON.stringify({ context, ...body }),
  });
  if (!response.ok) throw new Error(`Innertube ${path} failed: HTTP ${response.status}`);
  return response.json();
}

function textFromRuns(runs = []) {
  return runs.map((run) => run.text || '').join('');
}

function firstRendererOfType(root, rendererName) {
  if (!root || typeof root !== 'object') return null;
  if (root[rendererName]) return root[rendererName];
  for (const value of Object.values(root)) {
    const found = firstRendererOfType(value, rendererName);
    if (found) return found;
  }
  return null;
}

function collectResponsiveRenderers(root, output = []) {
  if (!root || typeof root !== 'object') return output;
  if (root.musicResponsiveListItemRenderer) output.push(root.musicResponsiveListItemRenderer);
  for (const value of Object.values(root)) collectResponsiveRenderers(value, output);
  return output;
}

function rendererText(renderer) {
  const parts = [];
  for (const column of renderer.flexColumns || []) {
    const runs = column.musicResponsiveListItemFlexColumnRenderer?.text?.runs || [];
    parts.push(textFromRuns(runs));
  }
  const fixedRuns = renderer.fixedColumns?.flatMap((column) => column.musicResponsiveListItemFixedColumnRenderer?.text?.runs || []) || [];
  parts.push(textFromRuns(fixedRuns));
  return parts.filter(Boolean).join(' ');
}

function scoreRenderer(renderer, needle) {
  const text = normalize(rendererText(renderer));
  let score = 0;
  if (needle.title && text.includes(needle.title)) score += 8;
  if (needle.artist && text.includes(needle.artist)) score += 4;
  if (needle.query && text.includes(needle.query)) score += 2;
  if (text.includes('song')) score += 2;
  if (text.includes('video')) score -= 1;
  return score;
}

function findQueueEndpoint(renderer, insertPosition) {
  const items = renderer.menu?.menuRenderer?.items || [];
  for (const item of items) {
    const endpoint = item.menuServiceItemRenderer?.serviceEndpoint;
    const queueAddEndpoint = endpoint?.queueAddEndpoint;
    if (queueAddEndpoint?.queueInsertPosition === insertPosition) return queueAddEndpoint;
  }
  return null;
}

async function resolveQueueTarget(job, insertPosition) {
  const needle = candidateNeedle(job);
  if (needle.videoId) {
    return {
      videoId: needle.videoId,
      title: job.candidate?.title || job.query || needle.videoId,
      params: '',
    };
  }

  const search = await innertubeFetch('search', { query: job.query || job.candidate?.title || '' });
  // Uses the non-navigating /youtubei/v1/search endpoint; never location.href-searches the active player tab.
  const renderers = collectResponsiveRenderers(search)
    .map((renderer) => ({ renderer, score: scoreRenderer(renderer, needle), text: rendererText(renderer) }))
    .sort((a, b) => b.score - a.score);

  for (const entry of renderers) {
    const queueAddEndpoint = findQueueEndpoint(entry.renderer, insertPosition);
    const target = queueAddEndpoint?.queueTarget;
    if (target?.videoId) {
      return {
        videoId: target.videoId,
        backingQueuePlaylistId: target.backingQueuePlaylistId,
        params: queueAddEndpoint.params || '',
        title: entry.text || job.query || target.videoId,
      };
    }
  }

  const fallback = firstRendererOfType(search, 'musicResponsiveListItemRenderer');
  const fallbackEndpoint = fallback && findQueueEndpoint(fallback, insertPosition);
  const fallbackTarget = fallbackEndpoint?.queueTarget;
  if (fallbackTarget?.videoId) {
    return {
      videoId: fallbackTarget.videoId,
      backingQueuePlaylistId: fallbackTarget.backingQueuePlaylistId,
      params: fallbackEndpoint.params || '',
      title: rendererText(fallback) || job.query || fallbackTarget.videoId,
    };
  }

  throw new Error('Could not resolve a queue target from YouTube Music search');
}

function queueController() {
  const controller = document.querySelector('ytmusic-player-queue');
  if (!controller?.getState || !controller?.dispatch) {
    throw new Error('YouTube Music queue controller is not available');
  }
  return controller;
}

function serverQueueItems(response) {
  return (response.queueDatas || [])
    .map((queueData) => queueData.content)
    .filter(Boolean);
}

function insertQueueItems(items, insertPosition) {
  if (!items.length) throw new Error('YouTube Music returned no queue items to insert');

  const controller = queueController();
  const state = controller.getState();
  const currentIndex = state.queue?.selectedItemIndex ?? 0;
  const existingItems = state.queue?.items || [];
  const index = insertPosition === PLAY_NEXT_INSERT_POSITION ? currentIndex + 1 : existingItems.length;

  controller.dispatch({
    type: 'ADD_ITEMS',
    payload: {
      nextQueueItemId: state.queue?.nextQueueItemId,
      index,
      items,
      shouldAssignIds: true,
    },
  });

  return { index, count: items.length };
}

async function addQueueTarget(target, insertPosition) {
  const body = {
    videoIds: [target.videoId],
    queueInsertPosition: insertPosition,
  };
  if (target.backingQueuePlaylistId) body.playlistId = target.backingQueuePlaylistId;
  if (target.params) body.params = target.params;

  const response = await innertubeFetch('music/get_queue', {
    // Fetches queue item data via /youtubei/v1/music/get_queue without route/navigation changes.
    // Equivalent queueAddEndpoint intent: queueInsertPosition: 'INSERT_AFTER_CURRENT_VIDEO'.
    ...body,
  });
  const inserted = insertQueueItems(serverQueueItems(response), insertPosition);
  return { response, inserted };
}

function queueItems() {
  const stateItems = (() => {
    try {
      const state = queueController().getState();
      return (state.queue?.items || [])
        .map(queueStateItemText)
        .filter(Boolean);
    } catch (_) {
      return [];
    }
  })();
  if (stateItems.length) return stateItems;

  return QUEUE_ITEM_SELECTORS.flatMap((selector) => [...document.querySelectorAll(selector)])
    .map((node) => normalize(node.innerText || node.textContent || ''))
    .filter(Boolean);
}

function queueStateItemText(item) {
  const renderer = item?.playlistPanelVideoRenderer
    || item?.playlistPanelVideoWrapperRenderer?.primaryRenderer?.playlistPanelVideoRenderer
    || item?.playlistPanelVideoWrapperRenderer?.counterpart?.playlistPanelVideoRenderer;
  if (!renderer) return '';
  return normalize([
    textFromRuns(renderer.title?.runs || []),
    textFromRuns(renderer.shortBylineText?.runs || []),
    textFromRuns(renderer.longBylineText?.runs || []),
    textFromRuns(renderer.lengthText?.runs || []),
    renderer.videoId || '',
  ].filter(Boolean).join(' '));
}

async function openQueuePanelIfPossible() {
  const existing = queueItems();
  if (existing.length) return existing;

  const buttons = [...document.querySelectorAll('button, tp-yt-paper-icon-button')];
  const queueButton = buttons.find((button) => normalize(button.getAttribute('aria-label') || button.title || '').includes('queue'));
  if (queueButton) {
    queueButton.click();
    await sleep(800);
  }
  return queueItems();
}

async function verifyQueueInsertion(target, job) {
  const needle = candidateNeedle(job);
  return waitFor(async () => {
    const items = await openQueuePanelIfPossible();
    const haystacks = items.slice(0, 10);
    const match = haystacks.find((text) => {
      if (target.videoId && text.includes(normalize(target.videoId))) return true;
      if (needle.title && text.includes(needle.title)) return true;
      if (needle.artist && text.includes(needle.artist) && (needle.title ? text.includes(needle.title) : true)) return true;
      const titleWords = (job.candidate?.title || job.query || '').toLowerCase().split(/\s+/).filter((word) => word.length > 2);
      return titleWords.length >= 2 && titleWords.slice(0, 3).every((word) => text.includes(word));
    });
    return match || null;
  }, 5000, 500);
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

  const insertPosition = job.intent === 'play_next' ? PLAY_NEXT_INSERT_POSITION : ADD_TO_QUEUE_INSERT_POSITION;
  const action = job.intent === 'play_next' ? 'Play next' : 'Add to queue';
  const target = await resolveQueueTarget(job, insertPosition);
  await addQueueTarget(target, insertPosition);
  const verified = await verifyQueueInsertion(target, job);
  if (!verified) {
    throw new Error('Could not verify queue insertion in Up Next after non-navigating queue API call');
  }

  return {
    ok: true,
    detail: `${action}: ${target.title}`,
    nowPlaying: currentNowPlaying() || null,
    verifiedQueueItem: verified,
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
