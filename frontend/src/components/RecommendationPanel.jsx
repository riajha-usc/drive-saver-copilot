const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function percent(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export default function RecommendationPanel({
  assetId,
  status,
  recommendation,
  error,
  hoursToWindow,
  onHoursChange,
  onGenerate,
  applyStatus,
  applyResult,
  applyError,
  onApply,
}) {
  if (!assetId) {
    return (
      <div className="recommendation-empty">
        <div className="agent-message">
          <div className="agent-avatar">●</div>
          <p>Select a motor asset to begin prescriptive analysis.</p>
        </div>
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div className="recommendation-state">
        <div className="recommendation-spinner" />
        <strong>Running counterfactual simulations...</strong>
        <p>Testing safe torque and speed adjustments.</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="recommendation-state">
        <p className="error-text">{error}</p>

        <button className="generate-button" onClick={onGenerate}>
          Try Again
        </button>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="recommendation-empty">
        <div className="agent-message">
          <div className="agent-avatar">●</div>

          <p>
            {assetId} is ready. Run the agent to calculate a safe adjustment.
          </p>
        </div>

        <label className="maintenance-window">
          <span>Hours until planned maintenance</span>

          <input
                       type="number"
            min="1"
            max="2000"
            value={hoursToWindow}
            onChange={(event) => onHoursChange(event.target.value)}
          />
        </label>

        <button className="generate-button" onClick={onGenerate}>
          GET RECOMMENDATION
        </button>
      </div>
    );
  }

  const { narrative, adjustments, projection, economics } = recommendation;
  const canApply = adjustments.length > 0;
  const applyCompleted = applyStatus === "ready";

  return (
    <div className="recommendation-result">
      <div className="recommendation-headline">
        <span className="action-badge">
          {recommendation.action_type.replaceAll("_", " ")}
        </span>

        <h3>{narrative.headline}</h3>
        <p>{narrative.explanation}</p>
      </div>

      <div className="adjustment-card">
        <h4>PRESCRIBED ADJUSTMENT</h4>

        {adjustments.length === 0 && (
          <p>No setpoint adjustment is recommended.</p>
        )}

        {adjustments.map((adjustment) => (
          <div className="adjustment-row" key={adjustment.parameter}>
            <div>
              <strong>{adjustment.label}</strong>
              <span>{adjustment.unit}</span>
            </div>

            <div className="adjustment-values">
              <span>{adjustment.current_value}</span>
              <b>→</b>
              <strong>{adjustment.recommended_value}</strong>
            </div>

            <small>{adjustment.change_pct.toFixed(1)}%</small>
          </div>
        ))}

        <div className="operator-instruction">
          {narrative.operator_instruction}
        </div>
      </div>

      <div className="projection-card">
        <Metric
          label="Projected RUL extension"
          value={`+${projection.rul_extension_hours.toFixed(1)} hours`}
        />

        <Metric
          label="Failure risk"
          value={`${percent(projection.baseline_failure_probability)} → ${percent(
            projection.projected_failure_probability,
          )}`}
        />

        <Metric
          label="Throughput loss"
          value={`${projection.throughput_loss_pct.toFixed(1)}%`}
        />

        <Metric
          label="Net economic benefit"
          value={currency.format(economics.net_benefit_usd)}
        />
      </div>

      <div className="recommendation-meta">
        <span>
          Confidence: {(recommendation.confidence * 100).toFixed(0)}%
        </span>

        <span>
          Maintenance window:{" "}
          {projection.reaches_maintenance_window ? "Reached" : "Not reached"}
        </span>
      </div>

      {recommendation.caveats.length > 0 && (
        <div className="caveat-box">
          <strong>Caveats</strong>

          <ul>
            {recommendation.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="economics-details">
        <summary>Economic assumptions</summary>

        <div>
          {Object.entries(economics.assumptions).map(([name, value]) => (
            <p key={name}>
              <span>{name.replaceAll("_", " ")}</span>
              <strong>{value}</strong>
            </p>
          ))}
        </div>
      </details>

      {applyError && <div className="apply-error">{applyError}</div>}

      {applyResult && <ApplyResult result={applyResult} />}

      <button
        className="implement-button"
        onClick={onApply}
        disabled={!canApply || applyStatus === "loading" || applyCompleted}
      >
        {applyStatus === "loading"
          ? "RECORDING ADJUSTMENT..."
          : applyCompleted
            ? "ADJUSTMENT RECORDED"
            : canApply
              ? "VET & IMPLEMENT ADJUSTMENT"
              : "NO ADJUSTMENT AVAILABLE"}
      </button>
    </div>
  );
}

function ApplyResult({ result }) {
  return (
    <div className="apply-result">
      <div className="apply-result-header">
        <strong>ADJUSTMENT RECORDED</strong>
        <span>Prototype simulation</span>
      </div>

      <Comparison
        label="Torque"
        before={`${result.before.torque} Nm`}
        after={`${result.after.torque} Nm`}
      />

      <Comparison
        label="Rotational speed"
        before={`${result.before.rotational_speed} RPM`}
        after={`${result.after.rotational_speed} RPM`}
      />

      <Comparison
        label="Failure probability"
        before={percent(result.failure_probability_before)}
        after={percent(result.failure_probability_after)}
      />

      <Comparison
        label="Remaining useful life"
        before={`${result.rul_hours_before} hours`}
        after={`${result.rul_hours_after} hours`}
      />

      <p className="applied-note">{result.applied_note}</p>
    </div>
  );
}

function Comparison({ label, before, after }) {
  return (
    <div className="comparison-row">
      <span>{label}</span>

      <div>
        <small>{before}</small>
        <b>→</b>
        <strong>{after}</strong>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="projection-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}