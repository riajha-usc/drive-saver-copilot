/*
 * The model selection behind every prediction on this dashboard.
 *
 * Each failure model was picked from three candidates on validation PR AUC;
 * the test split only reports results. PR AUC suits rare events like failures,
 * where plain accuracy looks excellent for a model that never predicts one.
 */
const HEAD_LABELS = {
  machine_failure: "Overall failure risk",
  HDF: "Heat dissipation",
  PWF: "Power",
  OSF: "Overstrain",
  TWF: "Tool wear",
};

function score(value) {
  return value === null || value === undefined ? "n/a" : value.toFixed(3);
}

export default function ModelComparison({ model }) {
  const selection = model?.metrics?.selection;

  if (!selection) {
    return (
      <p className="models-state">
        Model comparison is not available for this build. Retrain with
        make train.
      </p>
    );
  }

  return (
    <div className="models-view">
      <p className="models-intro">
        Every failure model was chosen from three candidates on{" "}
        <strong>validation PR AUC</strong>. The test split is held out and only
        reports results. Logistic regression is a baseline: root cause analysis
        needs a tree model, so it is measured but never chosen.
      </p>

      <div className="models-list">
        {Object.entries(selection).map(([head, entry]) => {
          const test = model.metrics.heads?.[head];
          return (
            <div className="models-head" key={head}>
              <div className="models-head-title">
                <strong>{HEAD_LABELS[head] ?? head}</strong>
                <span>
                  Test PR AUC {score(test?.pr_auc)}
                </span>
              </div>

              {entry.candidates.map((candidate) => {
                const chosen = candidate.name === entry.chosen;
                const width = Math.max(
                  (candidate.val_pr_auc ?? 0) * 100,
                  2,
                );
                return (
                  <div
                    key={candidate.name}
                    className={`models-row ${chosen ? "chosen" : ""} ${
                      candidate.eligible ? "" : "baseline"
                    }`}
                  >
                    <span className="models-name">
                      {candidate.label}
                      {chosen && <em>chosen</em>}
                    </span>
                    <div className="models-bar-track">
                      <div
                        className="models-bar"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className="models-score">
                      {score(candidate.val_pr_auc)}
                    </span>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <p className="models-footer">
        Every candidate is tracked in MLflow during training. Tool wear stays low
        for all three: the dataset places those failures at random inside the
        wear window, so no feature can time them.
      </p>
    </div>
  );
}
