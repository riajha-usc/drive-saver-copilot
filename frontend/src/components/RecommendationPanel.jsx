import { useEffect, useState } from "react";

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
  onGenerate,
  applyStatus,
  applyResult,
  applyError,
  onApply,
}) {
  const [activeView, setActiveView] = useState("summary");

  /*
   * Return to the recommendation summary when the selected
   * asset or recommendation changes.
   */
  useEffect(() => {
    setActiveView("summary");
  }, [assetId, recommendation]);

  /*
   * Automatically open the simulated result after an
   * adjustment is recorded.
   */
  useEffect(() => {
    if (applyResult) {
      setActiveView("applied");
    }
  }, [applyResult]);

  if (!assetId) {
    return (
      <div className="recommendation-empty">
        <div className="agent-message">
          <div className="agent-avatar">●</div>

          <p>
            Select a motor asset to begin prescriptive
            analysis.
          </p>
        </div>
      </div>
    );
  }

  /*
   * Show API errors before checking for an empty recommendation.
   */
  if (status === "error") {
    return (
      <div className="recommendation-state">
        <p className="error-text">
          {error || "Could not generate a recommendation."}
        </p>

        <button
          type="button"
          className="generate-button"
          onClick={onGenerate}
        >
          TRY AGAIN
        </button>
      </div>
    );
  }

  /*
   * App.jsx automatically requests the recommendation.
   * Therefore, no Get Recommendation button is needed here.
   */
  if (status === "loading" || !recommendation) {
    return (
      <div className="recommendation-state">
        <div className="recommendation-spinner" />

        <strong>Generating recommendation...</strong>

        <p>
          Testing safe torque and speed adjustments for{" "}
          {assetId}.
        </p>
      </div>
    );
  }

  const { narrative, projection, economics } =
    recommendation;

  const adjustments = recommendation.adjustments || [];
  const caveats = recommendation.caveats || [];
  const assumptions = economics?.assumptions || {};

  const canApply = adjustments.length > 0;
  const applyCompleted = applyStatus === "ready";

  return (
    <div className="recommendation-workspace">
      <div className="recommendation-workspace-header">
        <span className="action-badge">
          {recommendation.action_type.replaceAll("_", " ")}
        </span>

        <strong>{narrative.headline}</strong>
      </div>

      <div className="recommendation-view">
        {activeView === "summary" && (
          <RecommendationSummary
            narrative={narrative}
            adjustments={adjustments}
            projection={projection}
            economics={economics}
            caveats={caveats}
            hasApplyResult={Boolean(applyResult)}
            onOpen={setActiveView}
          />
        )}

        {activeView === "adjustment" && (
          <AdjustmentView
            adjustments={adjustments}
            narrative={narrative}
            onBack={() => setActiveView("summary")}
          />
        )}

        {activeView === "impact" && (
          <ImpactView
            projection={projection}
            economics={economics}
            confidence={recommendation.confidence}
            onBack={() => setActiveView("summary")}
          />
        )}

        {activeView === "caveats" && (
          <CaveatsView
            caveats={caveats}
            onBack={() => setActiveView("summary")}
          />
        )}

        {activeView === "economics" && (
          <EconomicsView
            assumptions={assumptions}
            economics={economics}
            onBack={() => setActiveView("summary")}
          />
        )}

        {activeView === "applied" && applyResult && (
          <div className="recommendation-detail-view">
            <BackButton
              onClick={() => setActiveView("summary")}
            />

            <ApplyResult result={applyResult} />
          </div>
        )}
      </div>

      <div className="recommendation-footer">
        {applyError && (
          <div className="apply-error">
            {applyError}
          </div>
        )}

        <button
          type="button"
          className="implement-button"
          onClick={onApply}
          disabled={
            !canApply ||
            applyStatus === "loading" ||
            applyCompleted
          }
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
    </div>
  );
}

function RecommendationSummary({
  narrative,
  adjustments,
  projection,
  economics,
  caveats,
  hasApplyResult,
  onOpen,
}) {
  const assumptionCount = Object.keys(
    economics?.assumptions || {},
  ).length;

  return (
    <div className="recommendation-summary">
      <p className="recommendation-summary-text">
        {narrative.explanation}
      </p>

      <button
        type="button"
        className="recommendation-summary-card adjustment-summary"
        onClick={() => onOpen("adjustment")}
      >
        <div>
          <span>PRESCRIBED ADJUSTMENT</span>

          <strong>
            {adjustments.length > 0
              ? `${adjustments.length} setpoint ${
                  adjustments.length === 1
                    ? "change"
                    : "changes"
                }`
              : "No adjustment"}
          </strong>
        </div>

        <small>VIEW DETAILS</small>
      </button>

      <button
        type="button"
        className="recommendation-summary-card impact-summary"
        onClick={() => onOpen("impact")}
      >
        <div>
          <span>PROJECTED IMPACT</span>

          <strong>
            +{projection.rul_extension_hours.toFixed(1)}{" "}
            hours
          </strong>
        </div>

        <div className="summary-secondary-value">
          <span>Net benefit</span>

          <strong>
            {currency.format(economics.net_benefit_usd)}
          </strong>
        </div>
      </button>

      <div className="recommendation-summary-grid">
        <button
          type="button"
          className="recommendation-small-card"
          onClick={() => onOpen("caveats")}
        >
          <span>CAVEATS</span>
          <strong>{caveats.length}</strong>
        </button>

        <button
          type="button"
          className="recommendation-small-card"
          onClick={() => onOpen("economics")}
        >
          <span>ECONOMIC MODEL</span>
          <strong>{assumptionCount} inputs</strong>
        </button>
      </div>

      {hasApplyResult && (
        <button
          type="button"
          className="recommendation-recorded-card"
          onClick={() => onOpen("applied")}
        >
          <span>ADJUSTMENT RECORDED</span>
          <strong>View simulated result</strong>
        </button>
      )}
    </div>
  );
}

function AdjustmentView({
  adjustments,
  narrative,
  onBack,
}) {
  return (
    <div className="recommendation-detail-view">
      <BackButton onClick={onBack} />

      <div className="recommendation-detail-heading">
        <span>PRESCRIBED ADJUSTMENT</span>
        <h3>Recommended setpoint changes</h3>
      </div>

      <div className="adjustment-card">
        {adjustments.length === 0 && (
          <p>No setpoint adjustment is recommended.</p>
        )}

        {adjustments.map((adjustment) => (
          <div
            className="adjustment-row"
            key={adjustment.parameter}
          >
            <div>
              <strong>{adjustment.label}</strong>
              <span>{adjustment.unit}</span>
            </div>

            <div className="adjustment-values">
              <span>{adjustment.current_value}</span>
              <b>→</b>
              <strong>
                {adjustment.recommended_value}
              </strong>
            </div>

            <small>
              {adjustment.change_pct.toFixed(1)}%
            </small>
          </div>
        ))}

        <div className="operator-instruction">
          {narrative.operator_instruction}
        </div>
      </div>
    </div>
  );
}

function ImpactView({
  projection,
  economics,
  confidence,
  onBack,
}) {
  return (
    <div className="recommendation-detail-view">
      <BackButton onClick={onBack} />

      <div className="recommendation-detail-heading">
        <span>PROJECTED IMPACT</span>
        <h3>Expected operational outcome</h3>
      </div>

      <div className="projection-card">
        <Metric
          label="Projected RUL extension"
          value={`+${projection.rul_extension_hours.toFixed(
            1,
          )} hours`}
        />

        <Metric
          label="Failure risk"
          value={`${percent(
            projection.baseline_failure_probability,
          )} → ${percent(
            projection.projected_failure_probability,
          )}`}
        />

        <Metric
          label="Throughput loss"
          value={`${projection.throughput_loss_pct.toFixed(
            1,
          )}%`}
        />

        <Metric
          label="Net economic benefit"
          value={currency.format(
            economics.net_benefit_usd,
          )}
        />
      </div>

      <div className="recommendation-meta">
        <span>
          Confidence: {(confidence * 100).toFixed(0)}%
        </span>

        <span>
          Maintenance window:{" "}
          {projection.reaches_maintenance_window
            ? "Reached"
            : "Not reached"}
        </span>
      </div>
    </div>
  );
}

function CaveatsView({ caveats, onBack }) {
  return (
    <div className="recommendation-detail-view">
      <BackButton onClick={onBack} />

      <div className="recommendation-detail-heading">
        <span>CAUTION</span>
        <h3>Recommendation caveats</h3>
      </div>

      <div className="caveat-box">
        {caveats.length > 0 ? (
          <ul>
            {caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        ) : (
          <p>
            No caveats were returned for this
            recommendation.
          </p>
        )}
      </div>
    </div>
  );
}

function EconomicsView({
  assumptions,
  economics,
  onBack,
}) {
  return (
    <div className="recommendation-detail-view">
      <BackButton onClick={onBack} />

      <div className="recommendation-detail-heading">
        <span>ECONOMIC MODEL</span>
        <h3>Benefit assumptions</h3>
      </div>

      <div className="economics-summary">
        <span>Net economic benefit</span>

        <strong>
          {currency.format(economics.net_benefit_usd)}
        </strong>
      </div>

      <div className="economics-assumption-list">
        {Object.entries(assumptions).map(
          ([name, value]) => (
            <div key={name}>
              <span>
                {name.replaceAll("_", " ")}
              </span>

              <strong>{String(value)}</strong>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function BackButton({ onClick }) {
  return (
    <button
      type="button"
      className="recommendation-back-button"
      onClick={onClick}
    >
      ← BACK TO SUMMARY
    </button>
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
        before={percent(
          result.failure_probability_before,
        )}
        after={percent(
          result.failure_probability_after,
        )}
      />

      <Comparison
        label="Remaining useful life"
        before={`${result.rul_hours_before} hours`}
        after={`${result.rul_hours_after} hours`}
      />

      <p className="applied-note">
        {result.applied_note}
      </p>
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