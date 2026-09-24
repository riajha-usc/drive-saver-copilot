/*
 * What the agent did for the selected asset, one row per LangGraph node.
 *
 * While a request is in flight the nodes are listed as pending rather than
 * animated through, because the API returns them all at once. Showing them tick
 * off one by one would be inventing progress the server never reported.
 */
const NODES = [
  { node: "ingest", label: "Load the failure models" },
  { node: "diagnose", label: "Diagnose the asset" },
  { node: "simulate", label: "Simulate adjustments" },
  { node: "decide", label: "Choose an action" },
  { node: "narrate", label: "Write the explanation" },
  { node: "validate", label: "Validate the output" },
];

function formatDuration(ms) {
  return ms < 1 ? "<1 ms" : `${Math.round(ms)} ms`;
}

export default function AgentReasoning({
  hasSelection,
  status,
  reasoning,
  error,
}) {
  if (!hasSelection) {
    return (
      <p className="reasoning-state">
        Select an asset to see how the agent decides.
      </p>
    );
  }

  if (status === "error") {
    return <p className="reasoning-state error-text">{error}</p>;
  }

  if (status !== "ready" || !reasoning?.length) {
    return (
      <ol className="reasoning-list pending" aria-busy="true">
        {NODES.map((item, index) => (
          <li className="reasoning-step" key={item.node}>
            <span className="reasoning-marker">{index + 1}</span>
            <div>
              <strong>{item.label}</strong>
            </div>
          </li>
        ))}
      </ol>
    );
  }

  const totalMs = reasoning.reduce(
    (sum, step) => sum + step.duration_ms,
    0,
  );

  return (
    <>
      <ol className="reasoning-list">
        {reasoning.map((step) => (
          <li className="reasoning-step done" key={step.node}>
            <span className="reasoning-marker" aria-hidden="true">
              ✓
            </span>

            <div>
              <div className="reasoning-step-head">
                <strong>{step.title}</strong>
                <small>{formatDuration(step.duration_ms)}</small>
              </div>
              <p>{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>

      <p className="reasoning-footer">
        {reasoning.length} steps in {formatDuration(totalMs)}. Every figure
        comes from the model, the physics rules or the cost model; the
        language step only writes prose.
      </p>
    </>
  );
}
