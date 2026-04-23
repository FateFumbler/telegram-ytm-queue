const BACKEND = 'http://127.0.0.1:8015';

async function getYtmTab() {
  const tabs = await chrome.tabs.query({ url: '*://music.youtube.com/*' });
  return tabs.length > 0 ? tabs[0] : null;
}

async function pushState(tabId) {
  try {
    const state = await chrome.tabs.sendMessage(tabId, { type: 'ytm-state' });
    if (state?.nowPlaying) {
      await fetch(`${BACKEND}/api/extension/state`, {
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
    const tab = await getYtmTab();
    if (!tab?.id) return;

    await pushState(tab.id);

    const res = await fetch(`${BACKEND}/api/worker/jobs/next`);
    const data = await res.json();
    if (!data.job) return;

    const response = await chrome.tabs.sendMessage(tab.id, { type: 'ytm-queue-job', job: data.job });
    const ok = !!response?.ok;
    await fetch(`${BACKEND}/api/worker/jobs/${data.job.id}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ok,
        detail: response?.detail ? response.detail : (ok ? 'Extension executed queue action' : 'Extension failed to execute queue action'),
        worker_id: 'extension',
        now_playing: response?.nowPlaying ? response.nowPlaying : null,
        action: data.job.intent,
      }),
    });
  } catch (e) {
    console.debug('poll failed', e);
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('poll-backend', { periodInMinutes: 0.5 });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create('poll-backend', { periodInMinutes: 0.5 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'poll-backend') poll();
});
