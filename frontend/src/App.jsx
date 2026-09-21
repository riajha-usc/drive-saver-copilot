import { useEffect, useState } from "react";
import { getHealth, getModelInfo, listDatasets } from "./api";

// Scaffold only. It confirms the deployed container is serving both this app and
// the API from one origin, and it is the starting point for the dashboard tasks
// listed below. None of those are built yet.

function Row({ label, value }) {
  return (
    <div className="row">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

export default function App() {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    Promise.all([getHealth(), getModelInfo(), listDatasets()])
      .then(([health, model, datasets]) =>
        setState({ status: "ready", health, model, datasets })
      )
      .catch((error) => setState({ status: "error", error: error.message }));
  }, []);

  const { status, health, model, datasets, error } = state;
  const metrics = model?.metrics?.heads?.machine_failure;

  return (
    <div className="wrap">
      <h1>Drive-Saver Copilot</h1>
      <p className="sub">Prescriptive maintenance for VFDs and motors.</p>

      <h2>API</h2>
      <div className="panel">
        {status === "loading" && <p style={{ margin: 0 }}>Checking the API.</p>}

        {status === "error" && (
          <p style={{ margin: 0 }}>
            <span className="dot bad" />
            Could not reach the API: {error}
          </p>
        )}

        {status === "ready" && (
          <>
            <Row
              label="Status"
              value={
                <>
                  <span className={`dot ${health.status === "ok" ? "ok" : "warn"}`} />
                  {health.status}
                </>
              }
            />
            <Row label="Model loaded" value={health.model_loaded ? "yes" : "no"} />
            <Row label="Model trained" value={health.model_trained_at || "unknown"} />
            <Row label="Failure risk PR AUC" value={metrics ? metrics.pr_auc : "unknown"} />
            <Row
              label="Datasets"
              value={datasets.map((d) => `${d.name} (${d.row_count} rows)`).join(", ") || "none"}
            />
            <Row
              label="Assets at risk"
              value={datasets.reduce((n, d) => n + d.at_risk_count, 0)}
            />
          </>
        )}
      </div>

      <h2>Dashboard, not built yet</h2>
      <div className="panel">
        <ol>
          <li>
            <strong>Telemetry and failure alert interface.</strong> Asset selector,
            line charts for temperature, speed and torque, and a red alert box
            showing health status.
          </li>
          <li>
            <strong>Prescriptive recommendation panel.</strong> The prescribed
            parameter change, projected life extension in hours, estimated cost
            savings, and an Implement Adjustment button.
          </li>
          <li>
            <strong>End to end flow.</strong> Uploading a dataset triggers live
            predictions and populates the recommendation panel.
          </li>
        </ol>
      </div>

      <p className="note">
        Every endpoint is documented and executable at <a href="/docs">/docs</a>. The
        client for them is <code>src/api.js</code>, which uses relative paths because
        this app and the API are served from one origin.
      </p>
    </div>
  );
}
