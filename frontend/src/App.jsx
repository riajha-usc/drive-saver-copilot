import { useEffect, useState } from "react";
import { getHealth, getModelInfo, listDatasets } from "./api";
import DashboardHeader from "./components/DashboardHeader";
import Panel from "./components/Panel";

export default function App() {
  const [apiState, setApiState] = useState({
    status: "loading",
    health: null,
    model: null,
    error: "",
  });

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedAssetId] = useState("");

  useEffect(() => {
    Promise.all([getHealth(), getModelInfo(), listDatasets()])
      .then(([health, model, datasetList]) => {
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
        setApiState({
          status: "error",
          health: null,
          model: null,
          error: error.message,
        });
      });
  }, []);

  const selectedDataset = datasets.find(
    (dataset) => dataset.dataset_id === selectedDatasetId,
  );

  const apiStatus =
    apiState.status === "ready" ? apiState.health?.status : "loading";

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
                  <small>{dataset.row_count.toLocaleString()} rows</small>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="ASSET SELECTION">
            <div className="asset-placeholder">
              <span>+</span>
              <p>Asset table will appear here</p>
            </div>
          </Panel>
        </aside>

        <section className="center-column">
          <Panel
            title={
              selectedAssetId
                ? `MOTOR ASSET (${selectedAssetId})`
                : "MOTOR HEALTH OVERVIEW"
            }
            className="health-panel"
          >
            <div className="health-summary">
              <div className="health-gauge">
                <div className="gauge-arc">
                  <div className="gauge-value">--</div>
                </div>
                <span>HEALTH</span>
              </div>

              <div className="health-copy">
                <p className="critical-label">AWAITING ASSET SELECTION</p>
                <p>Select an asset to analyze</p>
                <strong>Live Health Status</strong>
              </div>
            </div>

            <div className="chart-placeholder">
              <div className="chart-grid-line" />
              <div className="chart-grid-line" />
              <div className="chart-grid-line" />

              <svg
                viewBox="0 0 800 180"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <polyline
                  className="placeholder-line primary-line"
                  points="0,145 90,135 170,130 250,108 330,120 410,70 500,110 585,45 670,95 800,55"
                />

                <polyline
                  className="placeholder-line secondary-line"
                  points="0,158 100,154 200,145 300,136 400,122 500,105 600,90 700,72 800,55"
                />
              </svg>
            </div>

            <div className="chart-legend">
              <span>
                <i className="legend-line red" />
                Process Temperature
              </span>

              <span>
                <i className="legend-line gray" />
                Torque
              </span>
            </div>
          </Panel>

          <Panel title="MODEL SANDBOX" className="sandbox-panel">
            <p className="section-label">ANALYSIS PIPELINE</p>

            <div className="timeline">
              <TimelineStep number="1" label="Dataset" active />
              <TimelineStep number="2" label="Asset Selection" />
              <TimelineStep number="3" label="Risk Analysis" />
              <TimelineStep number="4" label="Recommendation" />
              <TimelineStep number="5" label="Adjustment" />
            </div>

            <div className="model-summary">
              <span>
                Model:{" "}
                {apiState.health?.model_loaded ? "Loaded" : "Not loaded"}
              </span>

              <span>
                Assets at risk: {selectedDataset?.at_risk_count ?? "--"}
              </span>
            </div>
          </Panel>
        </section>

        <aside className="right-column">
          <Panel
            title="AGENTIC RECOMMENDATION ENGINE"
            className="recommendation-panel"
          >
            <div className="agent-message">
              <div className="agent-avatar">●</div>

              <p>
                Select a dataset and motor asset to begin the prescriptive
                analysis.
              </p>
            </div>

            <div className="recommendation-placeholder">
              <div className="recommendation-check">✓</div>

              <div>
                <strong>Prescribed adjustment</strong>
                <p>No recommendation generated yet.</p>
              </div>
            </div>

            <div className="benefit-card">
              <div>
                <strong>+ -- Hours</strong>
                <span>Projected RUL extension</span>
              </div>

              <div>
                <strong>$ --</strong>
                <span>Estimated cost savings</span>
              </div>
            </div>

            <button className="implement-button" disabled>
              VET &amp; IMPLEMENT ADJUSTMENT
            </button>
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
      <strong className={active ? "active-text" : ""}>{value}</strong>
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