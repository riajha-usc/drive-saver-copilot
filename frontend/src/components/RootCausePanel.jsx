function formatValue(value) {
  const number = Number(value);

  if (Math.abs(number) >= 100) {
    return number.toFixed(0);
  }

  return number.toFixed(2);
}

export default function RootCausePanel({
  detail,
  loading,
  error,
  hasSelection,
}) {
  if (!hasSelection) {
    return (
      <div className="root-cause-state">
        Select an asset to view its risk factors.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="root-cause-state">
        Calculating root causes...
      </div>
    );
  }

  if (error) {
    return <div className="root-cause-state error-text">{error}</div>;
  }

  if (!detail) {
    return null;
  }

  return (
    <div className="root-cause-layout">
      <div className="factor-section">
        <div className="root-cause-heading">
          <div>
            <span>DOMINANT CONTROLLABLE LEVER</span>
            <strong>{detail.dominant_lever || "None"}</strong>
          </div>
        </div>

        <div className="factor-list">
          {detail.factors.map((factor) => {
            const raisesRisk = factor.direction === "raises risk";
            const riskShare = factor.share_of_risk * 100;

            return (
              <div className="factor-item" key={factor.feature}>
                <div className="factor-label-row">
                  <div>
                    <strong>{factor.label}</strong>
                    <span>
                      {formatValue(factor.value)} {factor.unit}
                    </span>
                  </div>

                  <span
                    className={`factor-direction ${
                      raisesRisk ? "raises" : "lowers"
                    }`}
                  >
                    {factor.direction}
                  </span>
                </div>

                <div className="factor-bar-track">
                  <div
                    className={`factor-bar ${
                      raisesRisk ? "raises" : "lowers"
                    }`}
                    style={{
                      width: raisesRisk
                        ? `${Math.max(riskShare, 2)}%`
                        : "4%",
                    }}
                  />
                </div>

                <div className="factor-meta">
                  <span>SHAP {factor.shap_value.toFixed(4)}</span>

                  <span>
                    {raisesRisk
                      ? `${riskShare.toFixed(1)}% of upward risk`
                      : "Protective influence"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="margin-section">
        <p className="section-label">PHYSICAL OPERATING MARGINS</p>

        <div className="margin-list">
          {detail.margins.map((margin) => (
            <div
              key={margin.mode}
              className={`margin-item ${
                margin.violated ? "violated" : "safe"
              }`}
            >
              <div className="margin-title">
                <strong>{margin.label}</strong>

                <span>{margin.violated ? "VIOLATED" : "SAFE"}</span>
              </div>

              <p>
                Current: {formatValue(margin.value)} {margin.unit}
              </p>

              <p>
                Limit: {formatValue(margin.limit)} {margin.unit}
              </p>

              <p>
                Margin: {formatValue(margin.margin)} {margin.unit}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}