import { useState } from "react";

import { uploadDataset } from "../api";

/*
 * Uploading a telemetry CSV scores every row on the server. On success the
 * dashboard switches to the new dataset and opens its riskiest asset, so the
 * recommendation panel fills in without any further clicks.
 *
 * The limit mirrors MAX_UPLOAD_BYTES in backend/api/routers/telemetry.py, so an
 * oversized file is refused here instead of after a slow upload.
 */
const MAX_UPLOAD_BYTES = 16 * 1024 * 1024;

export default function DatasetUploader({ onUploaded }) {
  const [state, setState] = useState({
    status: "idle",
    summary: null,
    error: "",
  });

  async function handleFileChange(event) {
    const file = event.target.files?.[0];

    /*
     * Clear the input so choosing the same file again still fires onChange.
     */
    event.target.value = "";

    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setState({
        status: "error",
        summary: null,
        error: "Choose a .csv file.",
      });
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setState({
        status: "error",
        summary: null,
        error: "That file is larger than 16 MB.",
      });
      return;
    }

    setState({ status: "uploading", summary: null, error: "" });

    try {
      const summary = await uploadDataset(file);

      setState({ status: "ready", summary, error: "" });
      onUploaded(summary);
    } catch (error) {
      setState({
        status: "error",
        summary: null,
        error: error.message,
      });
    }
  }

  const uploading = state.status === "uploading";
  const summary = state.summary;

  return (
    <div className="dataset-uploader">
      <label
        className={`upload-button ${uploading ? "disabled" : ""}`}
      >
        {uploading
          ? "SCORING TELEMETRY..."
          : "UPLOAD TELEMETRY CSV"}

        <input
          type="file"
          accept=".csv,text/csv"
          disabled={uploading}
          onChange={handleFileChange}
        />
      </label>

      <p className="upload-message">
        AI4I columns: Type, air and process temperature, rotational
        speed, torque, tool wear.
      </p>

      {summary && (
        <div className="upload-success" role="status">
          <strong>
            {summary.row_count.toLocaleString()} rows scored
          </strong>

          <span>
            {summary.at_risk_count.toLocaleString()} at risk
            {summary.rows_rejected > 0
              ? `, ${summary.rows_rejected.toLocaleString()} unusable ${
                  summary.rows_rejected === 1 ? "row" : "rows"
                } skipped`
              : ""}
          </span>

          {summary.highest_risk_asset && (
            <span>
              Opened riskiest asset {summary.highest_risk_asset}
            </span>
          )}

          {summary.quality_verdict && (
            <span>
              Data quality:{" "}
              {{ ready: "ready", use_with_care: "use with care",
                 not_usable: "not usable" }[summary.quality_verdict]}
              , see the report below
            </span>
          )}
        </div>
      )}

      {state.status === "error" && (
        <div className="upload-error" role="alert">
          {state.error}
        </div>
      )}
    </div>
  );
}
