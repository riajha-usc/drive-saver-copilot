import { useEffect, useRef, useState } from "react";

import { getDatasetQuality } from "../api";

/*
 * Dataset quality report, opened from the dataset workspace.
 *
 * It answers whether a dataset is fit to predict on before anyone acts on a
 * prediction: which rows were skipped and why, whether readings sit inside the
 * range the model learned from, the product and failure mix, and how many rows
 * already breach a physical limit.
 */
export const VERDICT_LABELS = {
  ready: "Ready",
  use_with_care: "Use with care",
  not_usable: "Not usable",
};

const MODE_NAMES = {
  HDF: "Heat dissipation",
  PWF: "Power",
  OSF: "Overstrain",
  TWF: "Tool wear",
};

const STATUS_MARK = { pass: "✓", warn: "!", fail: "✕", info: "i" };

function fmt(value, digits = 1) {
  return value === null || value === undefined
    ? "n/a"
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function QualityReport({ datasetId, onClose }) {
  const [state, setState] = useState({ status: "loading", report: null, error: "" });
  const closeRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getDatasetQuality(datasetId)
      .then((report) => !cancelled && setState({ status: "ready", report, error: "" }))
      .catch((error) => !cancelled && setState({ status: "error", report: null, error: error.message }));
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  /*
   * Behave like a dialog: focus lands on Close, and Escape dismisses it.
   */
  useEffect(() => {
    closeRef.current?.focus();
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const report = state.report;

  return (
    <div className="quality-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section
        className="quality-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="quality-title"
      >
        <header className="quality-header">
          <div>
            <span>DATASET QUALITY REPORT</span>
            <h2 id="quality-title">{report?.name ?? "Loading"}</h2>
          </div>
          <button type="button" ref={closeRef} className="quality-close" onClick={onClose}>
            CLOSE
          </button>
        </header>

        {state.status === "loading" && <p className="quality-state">Profiling the dataset...</p>}
        {state.status === "error" && <p className="quality-state error-text">{state.error}</p>}

        {report && (
          <div className="quality-body">
            <div className={`quality-verdict ${report.verdict}`}>
              <strong>{VERDICT_LABELS[report.verdict]}</strong>
              <span>
                {report.rows_accepted.toLocaleString()} of{" "}
                {report.rows_received.toLocaleString()} rows usable
              </span>
            </div>

            <ul className="quality-checks">
              {report.checks.map((check) => (
                <li key={check.title} className={`quality-check ${check.status}`}>
                  <span className="quality-mark" aria-hidden="true">
                    {STATUS_MARK[check.status]}
                  </span>
                  <div>
                    <strong>{check.title}</strong>
                    <p>{check.detail}</p>
                  </div>
                </li>
              ))}
            </ul>

            {report.rejections.length > 0 && (
              <div className="quality-section">
                <h3>Why rows were skipped</h3>
                {report.rejections.map((r) => (
                  <div className="quality-row" key={r.reason}>
                    <span>{r.label}</span>
                    <strong>{r.count.toLocaleString()}</strong>
                  </div>
                ))}
              </div>
            )}

            <div className="quality-section">
              <h3>Readings against the training range</h3>
              <div className="quality-table" role="table">
                <div className="quality-table-row head" role="row">
                  <span role="columnheader">Signal</span>
                  <span role="columnheader">This dataset</span>
                  <span role="columnheader">Model trained on</span>
                  <span role="columnheader">Outside</span>
                </div>
                {report.columns.map((c) => (
                  <div
                    className={`quality-table-row ${c.out_of_range ? "flag" : ""}`}
                    role="row"
                    key={c.column}
                  >
                    <span role="cell">{c.label}</span>
                    <span role="cell">
                      {fmt(c.min)} to {fmt(c.max)} {c.unit}
                    </span>
                    <span role="cell">
                      {c.training_min === null
                        ? "n/a"
                        : `${fmt(c.training_min)} to ${fmt(c.training_max)} ${c.unit}`}
                    </span>
                    <span role="cell">{c.out_of_range.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="quality-grid">
              <div className="quality-section">
                <h3>Product mix</h3>
                {Object.entries(report.type_mix).map(([type, count]) => (
                  <div className="quality-row" key={type}>
                    <span>Quality {type}</span>
                    <strong>{count.toLocaleString()}</strong>
                  </div>
                ))}
              </div>

              <div className="quality-section">
                <h3>Rows already past a limit</h3>
                {Object.entries(report.limit_breaches).map(([mode, count]) => (
                  <div className="quality-row" key={mode}>
                    <span>{MODE_NAMES[mode] ?? mode}</span>
                    <strong>{count.toLocaleString()}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
