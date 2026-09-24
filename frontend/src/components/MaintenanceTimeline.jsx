/*
 * The whole idea in one picture: when the asset fails today, when the planned
 * maintenance window is, and when it fails after the prescribed change.
 *
 * Hours are the remaining useful life proxy, so the strip is labelled as an
 * estimate. The axis spans twice the window, or a little past today's failure
 * point when that is later. A projection beyond the axis is pinned to the right
 * edge and says so, instead of squashing everything else to fit 720 hours.
 */
const RUL_CAP_HOURS = 720;

function formatHours(hours) {
  return hours >= RUL_CAP_HOURS ? `${RUL_CAP_HOURS}+ h` : `${Math.round(hours)} h`;
}

function verdictFor(actionType, baseline, projected, window, showFix) {
  if (actionType === "stop_now") {
    return "No safe change reaches the window. Stop and repair.";
  }
  if (!showFix) {
    return baseline >= window
      ? "Lasts past the planned window with no change."
      : "Fails before the planned window.";
  }
  if (baseline < window && projected >= window) {
    return "Fails before the window today. With the change it lasts past it.";
  }
  if (baseline >= window) {
    return "Already lasts past the window. The change adds margin.";
  }
  return "The change buys time but still falls short of the window.";
}

export default function MaintenanceTimeline({ projection, actionType }) {
  const baseline = projection.baseline_rul_hours;
  const projected = projection.projected_rul_hours;
  const window = projection.hours_to_maintenance_window;

  const showFix =
    actionType !== "no_action" &&
    actionType !== "stop_now" &&
    projected > baseline;

  const axisMax = Math.max(window * 2, baseline * 1.25, 1);
  const position = (hours) => Math.min(hours / axisMax, 1) * 100;

  const nowAt = position(baseline);
  const windowAt = position(window);
  const fixAt = position(projected);
  const fixBeyond = showFix && projected > axisMax;

  return (
    <div
      className={`maintenance-timeline ${actionType}`}
      role="img"
      aria-label={
        `Failure in about ${formatHours(baseline)} now, planned maintenance at ` +
        `${formatHours(window)}` +
        (showFix ? `, failure after the change at ${formatHours(projected)}.` : ".")
      }
    >
      <div className="timeline-strip-head">
        <span>FAILURE TIMELINE</span>
        <small>estimated hours</small>
      </div>

      <div className="timeline-strip">
        <div className="timeline-strip-now" style={{ width: `${nowAt}%` }} />

        {showFix && (
          <div
            className="timeline-strip-fix"
            style={{ left: `${nowAt}%`, width: `${fixAt - nowAt}%` }}
          />
        )}

        <div className="timeline-strip-window" style={{ left: `${windowAt}%` }} />

        <span
          className="timeline-strip-dot now"
          style={{ left: `${nowAt}%` }}
        />

        {showFix && (
          <span
            className={`timeline-strip-dot fix ${fixBeyond ? "beyond" : ""}`}
            style={{ left: `${fixAt}%` }}
          />
        )}
      </div>

      <div className="timeline-strip-legend">
        <span className="now">Without change: {formatHours(baseline)}</span>
        <span className="window">Maintenance: {formatHours(window)}</span>
        {showFix && (
          <span className="fix">
            With change: {formatHours(projected)}
            {fixBeyond ? " (off scale)" : ""}
          </span>
        )}
      </div>

      <p className="timeline-strip-verdict">
        {verdictFor(actionType, baseline, projected, window, showFix)}
      </p>
    </div>
  );
}
