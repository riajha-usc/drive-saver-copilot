import { useEffect, useState } from "react";
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

import AssetHealth from "./components/AssetHealth";
import AssetTable from "./components/AssetTable";
import DashboardHeader from "./components/DashboardHeader";
import Panel from "./components/Panel";
import RecommendationPanel from "./components/RecommendationPanel";
import RootCausePanel from "./components/RootCausePanel";
import TelemetryCharts from "./components/TelemetryCharts";

export default function App() {
  const [apiState, setApiState] = useState({
    status: "loading",
    health: null,
    model: null,
    error: "",
  });

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedAssetId, setSelectedAssetId] = useState("");

  const [assetState, setAssetState] = useState({
    status: "idle",
    assets: [],
    error: "",
  });

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

  const [hoursToWindow, setHoursToWindow] = useState(48);

  const [recommendationState, setRecommendationState] = useState({
    status: "idle",
    recommendation: null,
    error: "",
  });

  const [applyState, setApplyState] = useState({
    status: "idle",
    result: null,
    error: "",
  });


  useEffect(() => {
    let cancelled = false;

    Promise.all([getHealth(), getModelInfo(), listDatasets()])
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

        if (datasetList.length > 0) {
          setSelectedDatasetId(datasetList[0].dataset_id);
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

  useEffect(() => {
    if (!selectedDatasetId) {
      setAssetState({
        status: "idle",
        assets: [],
        error: "",
      });

      return;
    }

    let cancelled = false;

    setSelectedAssetId("");

    setAssetState({
      status: "loading",
      assets: [],
      error: "",
    });

    listAssets(selectedDatasetId, {
      sort: "risk",
      limit: 25,
    })
      .then((response) => {
        if (cancelled) {
          return;
        }

        setAssetState({
          status: "ready",
          assets: response.assets,
          error: "",
        });
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setAssetState({
          status: "error",
          assets: [],
          error: error.message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDatasetId]);

  /*
   * Load full risk details whenever an asset is selected.
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
   * Load telemetry history whenever an asset is selected.
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

    getAssetHistory(selectedDatasetId, selectedAssetId, 60)
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
   * Clear the previous recommendation when the selected asset changes.
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
  }, [selectedDatasetId, selectedAssetId]);

  const selectedDataset = datasets.find(
    (dataset) => dataset.dataset_id === selectedDatasetId,
  );

  const apiStatus =
    apiState.status === "ready" ? apiState.health?.status : "loading";

  async function handleGenerateRecommendation() {
      if (!selectedDatasetId || !selectedAssetId) {
        return;
      }

      const hours = Number(hoursToWindow);

      if (!Number.isFinite(hours) || hours <= 0 || hours > 2000) {
        setRecommendationState({
          status: "error",
          recommendation: null,
          error: "Maintenance window must be between 1 and 2000 hours.",
        });

        return;
      }

      setRecommendationState({
        status: "loading",
        recommendation: null,
        error: "",
      });

      try {
        const recommendation = await getRecommendation(
          selectedDatasetId,
          selectedAssetId,
          hours,
        );

        setRecommendationState({
          status: "ready",
          recommendation,
          error: "",
        });
      } catch (error) {
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
            Number(hoursToWindow),
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

  return (
    <div className="app">
      <DashboardHeader apiStatus={apiStatus} />

      {apiState.status === "error" && (
        <div className="global-error">
          Could not connect to the local API: {apiState.error}
        </div>
      )}

      <main className="dashboard-grid">
        <aside className="left-column">
          <Panel title="AGENT ACTIVITY LOG">
            <p className="section-label">BACKGROUND PROCESSES</p>

            <div className="status-list">
              <StatusRow
                label="API connection"
                value={apiState.status === "ready" ? "Active" : "Waiting"}
                active={apiState.status === "ready"}
              />

              <StatusRow
                label="Failure model"
                value={apiState.health?.model_loaded ? "Active" : "Idle"}
                active={apiState.health?.model_loaded}
              />

              <StatusRow
                label="Recommendation agent"
                value={apiState.health?.model_loaded ? "Ready" : "Idle"}
                active={apiState.health?.model_loaded}
              />
            </div>
          </Panel>

          <Panel title="DATASET WORKSPACE">
            <p className="section-label">AVAILABLE DATASETS</p>

            <div className="dataset-list">
              {datasets.length === 0 && (
                <p className="empty-message">No datasets available.</p>
              )}

              {datasets.map((dataset) => (
                <button
                  key={dataset.dataset_id}
                  className={`dataset-option ${
                    selectedDatasetId === dataset.dataset_id ? "selected" : ""
                  }`}
                  onClick={() => setSelectedDatasetId(dataset.dataset_id)}
                >
                  <span>{dataset.name}</span>

                  <small>
                    {dataset.row_count.toLocaleString()} rows
                  </small>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="ASSET SELECTION">
            <AssetTable
              assets={assetState.assets}
              selectedAssetId={selectedAssetId}
              onSelect={setSelectedAssetId}
              loading={assetState.status === "loading"}
              error={assetState.error}
            />
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
              assetDetailState.detail?.asset?.risk_band ?? ""
            }`}
          >
            <AssetHealth
              detail={assetDetailState.detail}
              loading={assetDetailState.status === "loading"}
              error={assetDetailState.error}
              hasSelection={Boolean(selectedAssetId)}
            />
          </Panel>

          <Panel
            title="TELEMETRY HISTORY"
            className="telemetry-panel"
          >
            <TelemetryCharts
              points={historyState.points}
              note={historyState.note}
              loading={historyState.status === "loading"}
              error={historyState.error}
              hasSelection={Boolean(selectedAssetId)}
            />
          </Panel>

          <Panel
            title="ROOT CAUSE ANALYSIS"
            className="root-cause-panel"
          >
            <RootCausePanel
              detail={assetDetailState.detail}
              loading={assetDetailState.status === "loading"}
              error={assetDetailState.error}
              hasSelection={Boolean(selectedAssetId)}
            />
          </Panel>

          <Panel title="MODEL SANDBOX" className="sandbox-panel">
            <p className="section-label">ANALYSIS PIPELINE</p>

            <div className="timeline">
              <TimelineStep
                number="1"
                label="Dataset"
                active={Boolean(selectedDatasetId)}
              />

              <TimelineStep
                number="2"
                label="Asset Selection"
                active={Boolean(selectedAssetId)}
              />

              <TimelineStep
                number="3"
                label="Risk Analysis"
                active={assetDetailState.status === "ready"}
              />

              <TimelineStep
                number="4"
                label="Recommendation"
                active={recommendationState.status === "ready"}
              />
              <TimelineStep
                number="5"
                label="Adjustment"
                active={applyState.status === "ready"}
              />
            </div>

            <div className="model-summary">
              <span>
                Model:{" "}
                {apiState.health?.model_loaded
                  ? "Loaded"
                  : "Not loaded"}
              </span>

              <span>
                Assets at risk:{" "}
                {selectedDataset?.at_risk_count ?? "--"}
              </span>
            </div>
          </Panel>
        </section>

        <aside className="right-column">
          <Panel
            title="AGENTIC RECOMMENDATION ENGINE"
            className="recommendation-panel"
          >
            <RecommendationPanel
              assetId={selectedAssetId}
              status={recommendationState.status}
              recommendation={recommendationState.recommendation}
              error={recommendationState.error}
              hoursToWindow={hoursToWindow}
              onHoursChange={setHoursToWindow}
              onGenerate={handleGenerateRecommendation}
              applyStatus={applyState.status}
              applyResult={applyState.result}
              applyError={applyState.error}
              onApply={handleApplyAdjustment}
            />
          </Panel>
        </aside>
      </main>
    </div>
  );
}

function StatusRow({ label, value, active }) {
  return (
    <div className="status-row">
      <span>{label}</span>

      <strong className={active ? "active-text" : ""}>
        {value}
      </strong>
    </div>
  );
}

function TimelineStep({ number, label, active = false }) {
  return (
    <div className={`timeline-step ${active ? "active" : ""}`}>
      <div className="timeline-number">{number}</div>
      <span>{label}</span>
    </div>
  );
}