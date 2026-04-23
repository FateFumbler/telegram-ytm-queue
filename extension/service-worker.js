const BACKEND = 'http://127.0.0.1:8015';
const POLL_ALARM = 'poll-backend';
const IN_FLIGHT_KEY = 'ytmInFlightJobId';

async function getYtmTab() {
  const tabs = await chrome.tabs.query({ url: '*://music.youtube.com/*' });
  return tabs.length > 0 ? tabs[0] : null;
}

async function pushState(tabId) {
  try {
    const state = await chrome.tabs.sendMessage(tabId, { type: 'ytm-state' });
    if (state && state.nowPlaying) {
      await fetch(BACKEND + '/api/extension/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ now_playing: state.nowPlaying, source: 'extension' }),
      });
    }
  } catch (e) {
    console.debug('state push failed', e);
  }
}

async function poll() {
  try {
    const stored = await chrome.storage.local.get(IN_FLIGHT_KEY);
    if (stored && stored[IN_FLIGHT_KEY]) return;

    const tab = await getYtmTab();
    if (!tab || !tab.id) return;

    await pushState(tab.id);

    const res = await fetch(BACKEND + '/api/worker/jobs/next');
    const data = await res.json();
    if (!data.job) return;

    await chrome.storage.local.set({ [IN_FLIGHT_KEY]: data.job.id });

    if (data.job.intent !== 'skip') {
      const query = encodeURIComponent(data.job.query || (data.job.candidate && data.job.candidate.title) || '');
      await chrome.tabs.update(tab.id, { url: 'https://music.youtube.com/search?q=' + query });
      await waitForTabComplete(tab.id);
      await new Promise((resolve) => setTimeout(resolve, 2500));
    }

    const response = await chrome.tabs.sendMessage(tab.id, { type: 'ytm-queue-job', job: data.job });
    const ok = !!(response && response.ok);
    await fetch(BACKEND + '/api/worker/jobs/' + data.job.id + '/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ok,
        detail: response && response.detail ? response.detail : (ok ? 'Extension executed queue action' : 'Extension failed to execute queue action'),
        worker_id: 'extension',
        now_playing: response && response.nowPlaying ? response.nowPlaying : null,
        action: data.job.intent,
      }),
    });
    await chrome.storage.local.remove(IN_FLIGHT_KEY);
  } catch (e) {
    console.debug('poll failed', e);
    await chrome.storage.local.remove(IN_FLIGHT_KEY);
  }
}

function waitForTabComplete(tabId) {
  return new Promise((resolve) => {
    let done = false;
    const timeout = setTimeout(() => finish(), 12000);
    function finish() {
      if (done) return;
      done = true;
      clearTimeout(timeout);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }
    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === 'complete') finish();
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

function schedulePoll() {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: 0.5 });
}

chrome.runtime.onInstalled.addListener(() => {
  schedulePoll();
  poll();
});

chrome.runtime.onStartup.addListener(() => {
  schedulePoll();
  poll();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === POLL_ALARM) poll();
});

chrome.action.onClicked.addListener(() => {
  poll();
});

schedulePoll();
poll();
