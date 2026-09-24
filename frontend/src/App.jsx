import { useEffect, useRef, useState } from "react";

import {
  applyAdjustment,
  getAsset,
  getAssetHistory,
  getHealth,
  getModelInfo,
  getRecommendation,
  listAssets,
  listDatasets,
} from "./api";

import AgentReasoning from "./components/AgentReasoning";
import AssetFilters from "./components/AssetFilters";
import AssetHealth from "./components/AssetHealth";
import AssetTable from "./components/AssetTable";
import DashboardHeader from "./components/DashboardHeader";
import DatasetUploader from "./components/DatasetUploader";
import MaintenanceWindowControl from "./components/MaintenanceWindowControl";
import ModelComparison from "./components/ModelComparison";
import Panel from "./components/Panel";
import RecommendationPanel from "./components/RecommendationPanel";
import RootCausePanel from "./components/RootCausePanel";
import TelemetryCharts from "./components/TelemetryCharts";

const DEFAULT_MAINTENANCE_WINDOW_HOURS = 48;
const ASSET_PAGE_SIZE = 25;
const THEME_STORAGE_KEY = "drive-saver-theme";

/* Seeded by the API at startup; see DEFAULT_DATASET_ID in backend/api/store.py. */
const SAMPLE_DATASET_ID = "ai4i-sample";

/*
 * Browser storage can throw in a private window or when site data is blocked.
 * The theme is only a convenience, so fall back quietly instead of failing to
 * render the dashboard.
 */
function readSavedTheme() {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY) === "light"
      ? "light"
      : "dark";
  } catch {
    return "dark";
  }
}

function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Not remembering the theme is harmless.
  }
}

export default function App() {
  const recommendationRequestRef = useRef({
    key: "",
    promise: null,
  });

  const [theme, setTheme] = useState(readSavedTheme);

  const [apiState, setApiState] = useState({
    status: "loading",
    health: null,
    model: null,
    error: "",
  });

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] =
    useState("");
  const [selectedAssetId, setSelectedAssetId] = useState("");

  const [assetFilter, setAssetFilter] = useState("all");

  const [assetState, setAssetState] = useState({
    status: "idle",
    assets: [],
    total: 0,
    loadingMore: false,
    error: "",
  });

  const [windowHours, setWindowHours] = useState(
    DEFAULT_MAINTENANCE_WINDOW_HOURS,
  );

  const [assetDetailState, setAssetDetailState] = useState({
    status: "idle",
    detail: null,
    error: "",
  });

  const [historyState, setHistoryState] = useState({
    status: "idle",
    points: [],
    note: "",
    error: "",
  });

  const [recommendationState, setRecommendationState] =
    useState({
      status: "idle",
      recommendation: null,
      error: "",
    });

  const [applyState, setApplyState] = useState({
    status: "idle",
    result: null,
    error: "",
  });

  const [analysisTab, setAnalysisTab] =
    useState("root-cause");

  /*
   * Apply and remember the selected dashboard theme.
   */
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    saveTheme(theme);
  }, [theme]);

  /*
   * Selecting a dataset and an asset together means the effects below never
   * run with a new dataset and a stale asset id from the previous one.
   */
  function selectDataset(datasetId, assetId = "") {
    setSelectedDatasetId(datasetId);
    setSelectedAssetId(assetId);
  }

  /*
   * Load API health, model information and datasets.
   */
  useEffect(() => {
    let cancelled = false;

    Promise.all([
      getHealth(),
      getModelInfo(),
      listDatasets(),
    ])
      .then(([health, model, datasetList]) => {
        if (cancelled) {
          return;
        }

        setApiState({
          status: "ready",
          health,
          model,
          error: "",
        });

        setDatasets(datasetList);

        /*
         * The API lists the newest upload first. Uploads live on a shared
         * server, so defaulting to the newest would open whatever the last
         * visitor uploaded. Start on the bundled sample when it is there.
         */
        const initialDataset =
          datasetList.find(
            (dataset) => dataset.dataset_id === SAMPLE_DATASET_ID,
          ) ?? datasetList[0];

        if (initialDataset) {
          selectDataset(initialDataset.dataset_id);
        }
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setApiState({
          status: "error",
          health: null,
          model: null,
          error: error.message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  /*
   * Load the first page of assets when the dataset or the risk filter changes.
   */
  useEffect(() => {
    if (!selectedDatasetId) {
      setAssetState({
        status: "idle",
        assets: [],
        total: 0,
        loadingMore: false,
        error: "",
      });

      return;
    }

    let cancelled = false;

    setAssetState({
      status: "loading",
      assets: [],
      total: 0,
      loadingMore: false,
      error: "",
    });

    listAssets(selectedDatasetId, assetQuery(assetFilter, 0))
      .then((response) => {
        if (cancelled) {
          return;
        }

        setAssetState({
          status: "ready",
          assets: response.assets,
          total: response.total,
          loadingMore: false,
          error: "",
        });

        /*
         * Open the riskiest asset when nothing is selected yet, so the first
         * screen shows a diagnosis and a prescription instead of an empty
         * "select an asset" prompt. An existing selection is never replaced.
         */
        setSelectedAssetId(
          (current) => current || response.assets[0]?.asset_id || "",
        );
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setAssetState({
          status: "error",
          assets: [],
          total: 0,
          loadingMore: false,
          error: error.message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDatasetId, assetFilter]);

  /*
   * Load risk details for the selected asset.
   */
  useEffect(() => {
    if (!selectedDatasetId || !selectedAssetId) {
      setAssetDetailState({
        status: "idle",
        detail: null,
        error: "",
      });

      return;
    }

    let cancelled = false;

    setAssetDetailState({
      status: "loading",
      detail: null,
      error: "",
    });

    getAsset(selectedDatasetId, selectedAssetId)
      .then((detail) => {
        if (cancelled) {
          return;
        }

        setAssetDetailState({
          status: "ready",
          detail,
          error: "",
        });
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setAssetDetailState({
          status: "error",
          detail: null,
          error: error.message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDatasetId, selectedAssetId]);

  /*
   * Load telemetry for the selected asset.
   */
  useEffect(() => {
    if (!selectedDatasetId || !selectedAssetId) {
      setHistoryState({
        status: "idle",
        points: [],
        note: "",
        error: "",
      });

      return;
    }

    let cancelled = false;

    setHistoryState({
      status: "loading",
      points: [],
      note: "",
      error: "",
    });

    getAssetHistory(
      selectedDatasetId,
      selectedAssetId,
      60,
    )
      .then((history) => {
        if (cancelled) {
          return;
        }

        setHistoryState({
          status: "ready",
          points: history.points,
          note: history.note,
          error: "",
        });
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setHistoryState({
          status: "error",
          points: [],
          note: "",
          error: error.message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDatasetId, selectedAssetId]);

  /*
   * Reset asset-specific UI when the selection changes.
   */
  useEffect(() => {
    setRecommendationState({
      status: "idle",
      recommendation: null,
      error: "",
    });

    setApplyState({
      status: "idle",
      result: null,
      error: "",
    });

    setAnalysisTab("root-cause");
  }, [selectedDatasetId, selectedAssetId]);

  /*
   * Automatically generate a recommendation after an asset is selected, and
   * again whenever the maintenance window changes, because the window is part
   * of the question the agent is answering.
   */
  useEffect(() => {
    if (!selectedDatasetId || !selectedAssetId) {
      recommendationRequestRef.current = {
        key: "",
        promise: null,
      };

      return;
    }

    let cancelled = false;

    const requestKey = [
      selectedDatasetId,
      selectedAssetId,
      windowHours,
    ].join(":");

    let recommendationPromise;

    if (
      recommendationRequestRef.current.key ===
        requestKey &&
      recommendationRequestRef.current.promise
    ) {
      recommendationPromise =
        recommendationRequestRef.current.promise;
    } else {
      recommendationPromise = getRecommendation(
        selectedDatasetId,
        selectedAssetId,
        windowHours,
      );

      recommendationRequestRef.current = {
        key: requestKey,
        promise: recommendationPromise,
      };
    }

    setRecommendationState({
      status: "loading",
      recommendation: null,
      error: "",
    });

    recommendationPromise
      .then((recommendation) => {
        if (cancelled) {
          return;
        }

        setRecommendationState({
          status: "ready",
          recommendation,
          error: "",
        });
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setRecommendationState({
          status: "error",
          recommendation: null,
          error: error.message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDatasetId, selectedAssetId, windowHours]);

  const selectedDataset = datasets.find(
    (dataset) =>
      dataset.dataset_id === selectedDatasetId,
  );

  const apiStatus =
    apiState.status === "ready"
      ? apiState.health?.status
      : "loading";

  /*
   * Retry recommendation generation after an API error.
   */
  async function handleGenerateRecommendation() {
    if (!selectedDatasetId || !selectedAssetId) {
      return;
    }

    setRecommendationState({
      status: "loading",
      recommendation: null,
      error: "",
    });

    const requestKey = [
      selectedDatasetId,
      selectedAssetId,
      windowHours,
    ].join(":");

    const recommendationPromise = getRecommendation(
      selectedDatasetId,
      selectedAssetId,
      windowHours,
    );

    recommendationRequestRef.current = {
      key: requestKey,
      promise: recommendationPromise,
    };

    try {
      const recommendation =
        await recommendationPromise;

      if (
        recommendationRequestRef.current.promise !==
        recommendationPromise
      ) {
        return;
      }

      setRecommendationState({
        status: "ready",
        recommendation,
        error: "",
      });
    } catch (error) {
      if (
        recommendationRequestRef.current.promise !==
        recommendationPromise
      ) {
        return;
      }

      setRecommendationState({
        status: "error",
        recommendation: null,
        error: error.message,
      });
    }
  }

  async function handleApplyAdjustment() {
    if (!selectedDatasetId || !selectedAssetId) {
      return;
    }

    setApplyState({
      status: "loading",
      result: null,
      error: "",
    });

    try {
      const result = await applyAdjustment(
        selectedDatasetId,
        selectedAssetId,
        windowHours,
      );

      setApplyState({
        status: "ready",
        result,
        error: "",
      });
    } catch (error) {
      setApplyState({
        status: "error",
        result: null,
        error: error.message,
      });
    }
  }

  /*
   * A recorded adjustment was computed for the old window, so it no longer
   * describes the prescription on screen.
   */
  function handleWindowChange(hours) {
    setWindowHours(hours);

    setApplyState({
      status: "idle",
      result: null,
      error: "",
    });
  }

  async function handleLoadMoreAssets() {
    if (!selectedDatasetId || assetState.loadingMore) {
      return;
    }

    const datasetId = selectedDatasetId;
    const filter = assetFilter;

    setAssetState((current) => ({
      ...current,
      loadingMore: true,
    }));

    try {
      const response = await listAssets(
        datasetId,
        assetQuery(filter, assetState.assets.length),
      );

      setAssetState((current) => ({
        ...current,
        assets: [...current.assets, ...response.assets],
        total: response.total,
        loadingMore: false,
      }));
    } catch (error) {
      setAssetState((current) => ({
        ...current,
        loadingMore: false,
        error: error.message,
      }));
    }
  }

  /*
   * Returns an error message for the finder, or an empty string on success.
   */
  async function handleJumpToAsset(assetId) {
    if (!selectedDatasetId) {
      return "Load a dataset first.";
    }

    try {
      await getAsset(selectedDatasetId, assetId);
      setSelectedAssetId(assetId);
      return "";
    } catch {
      return `${assetId} is not in this dataset.`;
    }
  }

  /*
   * Switch to a freshly uploaded dataset and open its riskiest asset, so the
   * recommendation panel fills in straight away.
   */
  function handleUploaded(summary) {
    setDatasets((current) => [
      summary,
      ...current.filter(
        (dataset) =>
          dataset.dataset_id !== summary.dataset_id,
      ),
    ]);

    setAssetFilter("all");
    selectDataset(
      summary.dataset_id,
      summary.highest_risk_asset || "",
    );
  }

  function handleThemeToggle() {
    setTheme((currentTheme) =>
      currentTheme === "dark" ? "light" : "dark",
    );
  }

  function renderDatasetWorkspace() {
    return (
      <>
        <p className="section-label">
          AVAILABLE DATASETS
        </p>

        <div className="dataset-list">
          {datasets.length === 0 && (
            <p className="empty-message">
              No datasets available.
            </p>
          )}

          {datasets.map((dataset) => (
            <button
              type="button"
              key={dataset.dataset_id}
              className={`dataset-option ${
                selectedDatasetId === dataset.dataset_id
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                selectDataset(dataset.dataset_id)
              }
            >
              <span>{dataset.name}</span>

              <small>
                {dataset.row_count.toLocaleString()} rows
                {" · "}
                {dataset.at_risk_count.toLocaleString()} at
                risk
              </small>
            </button>
          ))}
        </div>

        <DatasetUploader onUploaded={handleUploaded} />
      </>
    );
  }

  const hasMoreAssets =
    assetState.status === "ready" &&
    assetState.assets.length < assetState.total;

  return (
    <div className="app">
      <DashboardHeader
        apiStatus={apiStatus}
        theme={theme}
        onThemeToggle={handleThemeToggle}
      />

      {apiState.status === "error" && (
        <div className="global-error">
          Could not reach the Drive-Saver API:{" "}
          {apiState.error}
        </div>
      )}

      <main className="dashboard-grid">
        <aside className="left-column">
          <Panel title="SYSTEM STATUS">
            <p className="section-label">SERVICES</p>

            <div className="status-list">
              <StatusRow
                label="API connection"
                value={
                  apiState.status === "ready"
                    ? "Active"
                    : "Waiting"
                }
                active={apiState.status === "ready"}
              />

              <StatusRow
                label="Failure model"
                value={
                  apiState.health?.model_loaded
                    ? "Active"
                    : "Idle"
                }
                active={apiState.health?.model_loaded}
              />

              <StatusRow
                label="Recommendation agent"
                value={
                  apiState.health?.model_loaded
                    ? "Ready"
                    : "Idle"
                }
                active={apiState.health?.model_loaded}
              />
            </div>
          </Panel>

          <Panel
            title="ASSET SELECTION"
            className="asset-selection-panel"
          >
            <AssetFilters
              band={assetFilter}
              onBandChange={setAssetFilter}
              bandCounts={selectedDataset?.risk_band_counts}
              onJump={handleJumpToAsset}
            />

            <AssetTable
              assets={assetState.assets}
              selectedAssetId={selectedAssetId}
              onSelect={setSelectedAssetId}
              loading={
                assetState.status === "loading"
              }
              error={assetState.error}
            />

            {assetState.status === "ready" &&
              assetState.total > 0 && (
                <div className="asset-list-footer">
                  <span>
                    Showing{" "}
                    {assetState.assets.length.toLocaleString()}{" "}
                    of {assetState.total.toLocaleString()}
                  </span>

                  {hasMoreAssets && (
                    <button
                      type="button"
                      className="load-more-button"
                      disabled={assetState.loadingMore}
                      onClick={handleLoadMoreAssets}
                    >
                      {assetState.loadingMore
                        ? "LOADING..."
                        : "LOAD MORE"}
                    </button>
                  )}
                </div>
              )}
          </Panel>
        </aside>

        <section className="center-column">
          <Panel
            title={
              selectedAssetId
                ? `MOTOR ASSET (${selectedAssetId})`
                : "MOTOR HEALTH OVERVIEW"
            }
            className={`health-panel ${
              assetDetailState.detail?.asset
                ?.risk_band ?? ""
            }`}
          >
            <AssetHealth
              detail={assetDetailState.detail}
              loading={
                assetDetailState.status === "loading"
              }
              error={assetDetailState.error}
              hasSelection={Boolean(selectedAssetId)}
            />
          </Panel>

          <Panel
            title="ASSET ANALYSIS"
            className="analysis-panel"
          >
            <div
              className="analysis-tabs"
              role="tablist"
              aria-label="Asset analysis views"
            >
              <button
                type="button"
                id="root-cause-tab"
                role="tab"
                aria-selected={
                  analysisTab === "root-cause"
                }
                aria-controls="root-cause-view"
                className={`analysis-tab ${
                  analysisTab === "root-cause"
                    ? "active"
                    : ""
                }`}
                onClick={() =>
                  setAnalysisTab("root-cause")
                }
              >
                ROOT CAUSE
              </button>

              <button
                type="button"
                id="telemetry-tab"
                role="tab"
                aria-selected={
                  analysisTab === "telemetry"
                }
                aria-controls="telemetry-view"
                className={`analysis-tab ${
                  analysisTab === "telemetry"
                    ? "active"
                    : ""
                }`}
                onClick={() =>
                  setAnalysisTab("telemetry")
                }
              >
                TELEMETRY HISTORY
              </button>

              <button
                type="button"
                id="models-tab"
                role="tab"
                aria-selected={analysisTab === "models"}
                aria-controls="models-view"
                className={`analysis-tab ${
                  analysisTab === "models" ? "active" : ""
                }`}
                onClick={() => setAnalysisTab("models")}
              >
                MODELS
              </button>
            </div>

            <div className="analysis-panel-content">
              {analysisTab === "root-cause" && (
                <div
                  id="root-cause-view"
                  className="analysis-tab-view"
                  role="tabpanel"
                  aria-labelledby="root-cause-tab"
                >
                  <RootCausePanel
                    detail={assetDetailState.detail}
                    loading={
                      assetDetailState.status ===
                      "loading"
                    }
                    error={assetDetailState.error}
                    hasSelection={Boolean(
                      selectedAssetId,
                    )}
                  />
                </div>
              )}

              {analysisTab === "telemetry" && (
                <div
                  id="telemetry-view"
                  className="analysis-tab-view"
                  role="tabpanel"
                  aria-labelledby="telemetry-tab"
                >
                  <TelemetryCharts
                    points={historyState.points}
                    note={historyState.note}
                    loading={
                      historyState.status === "loading"
                    }
                    error={historyState.error}
                    hasSelection={Boolean(
                      selectedAssetId,
                    )}
                    theme={theme}
                  />
                </div>
              )}

              {analysisTab === "models" && (
                <div
                  id="models-view"
                  className="analysis-tab-view"
                  role="tabpanel"
                  aria-labelledby="models-tab"
                >
                  <ModelComparison model={apiState.model} />
                </div>
              )}
            </div>
          </Panel>

          <Panel
            title="AGENT REASONING"
            className="sandbox-panel reasoning-panel"
          >
            <AgentReasoning
              hasSelection={Boolean(selectedAssetId)}
              status={recommendationState.status}
              reasoning={
                recommendationState.recommendation?.reasoning
              }
              error={recommendationState.error}
            />
          </Panel>
        </section>

        <aside className="right-column">
          <Panel
            title="AGENTIC RECOMMENDATION ENGINE"
            className="recommendation-panel"
          >
            <MaintenanceWindowControl
              value={windowHours}
              onChange={handleWindowChange}
              disabled={
                recommendationState.status === "loading"
              }
            />

            <RecommendationPanel
              assetId={selectedAssetId}
              status={recommendationState.status}
              recommendation={
                recommendationState.recommendation
              }
              error={recommendationState.error}
              onGenerate={
                handleGenerateRecommendation
              }
              applyStatus={applyState.status}
              applyResult={applyState.result}
              applyError={applyState.error}
              onApply={handleApplyAdjustment}
              windowHours={windowHours}
            />
          </Panel>

          <Panel
            title="DATASET WORKSPACE"
            className="right-dataset-panel"
          >
            {renderDatasetWorkspace()}
          </Panel>
        </aside>
      </main>
    </div>
  );
}

/*
 * Query for one page of the asset list. "all" sends no band so every risk band
 * comes back, still ordered riskiest first.
 */
function assetQuery(filter, offset) {
  const query = {
    sort: "risk",
    limit: ASSET_PAGE_SIZE,
    offset,
  };

  if (filter !== "all") {
    query.band = filter;
  }

  return query;
}

function StatusRow({ label, value, active }) {
  return (
    <div className="status-row">
      <span>{label}</span>

      <strong
        className={active ? "active-text" : ""}
      >
        {value}
      </strong>
    </div>
  );
}

