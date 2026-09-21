// API client.
//
// Every path is relative on purpose. In production FastAPI serves this app and
// the API from the same container, so the browser origin is already correct and
// there is no base URL to configure and no CORS to negotiate. In development
// vite.config.js proxies these prefixes to a local API.

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      // Not every error body is JSON. Fall back to the status text.
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const getHealth = () => request("/health");
export const getModelInfo = () => request("/model");
export const listDatasets = () => request("/datasets");
export const getDataset = (id) => request(`/datasets/${id}`);

export const listAssets = (id, params = {}) =>
  request(`/datasets/${id}/assets?${new URLSearchParams({ limit: 50, sort: "risk", ...params })}`);

export const getAsset = (id, assetId) => request(`/datasets/${id}/assets/${assetId}`);

export const getAssetHistory = (id, assetId, window = 60) =>
  request(`/datasets/${id}/assets/${assetId}/history?window=${window}`);

export const getRecommendation = (id, assetId, hoursToWindow = 48) =>
  request(`/datasets/${id}/assets/${assetId}/recommendation?hours_to_window=${hoursToWindow}`, {
    method: "POST",
  });

export const applyAdjustment = (id, assetId, hoursToWindow = 48) =>
  request(`/datasets/${id}/assets/${assetId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hours_to_window: hoursToWindow }),
  });

export const uploadDataset = (file) => {
  const body = new FormData();
  body.append("file", file);
  return request("/datasets", { method: "POST", body });
};
