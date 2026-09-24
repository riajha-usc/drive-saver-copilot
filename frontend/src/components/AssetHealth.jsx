function formatNumber(value, decimals = 1) {
  return Number(value).toFixed(decimals);
}

export default function AssetHealth({
  detail,
  loading,
  error,
  hasSelection,
}) {
  if (!hasSelection) {
    return (
      <div className="health-state">
        <strong>Select an asset</strong>
        <p>Choose a motor from the asset table to view its health.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="health-state">
        Analyzing selected asset...
      </div>
    );
  }

  if (error) {
    return (
      <div className="health-state error-text">
        {error}
      </div>
    );
  }

  if (!detail) {
    return null;
  }

  const { asset } = detail;
  const failureRisk = asset.failure_probability * 100;
  const healthScore = Math.max(0, Math.min(100, 100 - failureRisk));

  /*
   * Very small SVG arcs with rounded ends appear as two dots.
   * Hide the progress path when health is below 1%.
   */
  const showHealthArc = healthScore >= 1;

  return (
    <div className={`asset-health ${asset.risk_band}`}>
      <div className="asset-health-summary">
        <div className="dynamic-gauge">
          <svg
            viewBox="0 0 120 68"
            role="img"
            aria-label={`${formatNumber(healthScore, 1)} percent health`}
          >
            <path
              className="gauge-background"
              pathLength="100"
              d="M 10 60 A 50 50 0 0 1 110 60"
            />

            {showHealthArc && (
              <path
                className="gauge-progress"
                pathLength="100"
                strokeDasharray={`${healthScore} 100`}
                d="M 10 60 A 50 50 0 0 1 110 60"
              />
            )}
          </svg>

          <div className="dynamic-gauge-value">
            {formatNumber(healthScore, 1)}%
          </div>

          <span>HEALTH</span>
        </div>

        <div className="asset-health-message">
          <p className="risk-label">
            {asset.risk_band} health
          </p>

          <strong>{detail.likely_failure_mode_name}</strong>

          <p>
            Failure risk: {formatNumber(failureRisk)}% · Estimated RUL:{" "}
            {formatNumber(asset.rul_hours)} hours
          </p>
        </div>
      </div>

      <div className="telemetry-summary">
        <TelemetryValue
          label="Process temperature"
          value={`${formatNumber(asset.process_temperature)} K`}
        />

        <TelemetryValue
          label="Rotational speed"
          value={`${formatNumber(asset.rotational_speed, 0)} RPM`}
        />

        <TelemetryValue
          label="Torque"
          value={`${formatNumber(asset.torque)} Nm`}
        />

        <TelemetryValue
          label="Shaft power"
          value={`${formatNumber(asset.shaft_power_w, 0)} W`}
        />
      </div>

      <div className="health-details">
        <div>
          <span>Dominant controllable lever</span>
          <strong>{detail.dominant_lever || "None"}</strong>
        </div>

        <div>
          <span>Physical rule violations</span>

          <strong>
            {asset.rule_violations.length > 0
              ? asset.rule_violations.join(", ")
              : "None"}
          </strong>
        </div>
      </div>
    </div>
  );
}

function TelemetryValue({ label, value }) {
  return (
    <div className="telemetry-value">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}