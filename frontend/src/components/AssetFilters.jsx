import { useState } from "react";

/*
 * The asset list is sorted by risk, so without a filter only the most critical
 * assets are ever reachable. These controls open up the rest of the fleet,
 * including healthy assets where the agent correctly recommends no action.
 */
const BANDS = [
  { value: "all", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "elevated", label: "Elevated" },
  { value: "normal", label: "Normal" },
];

/*
 * Accepts "VFD-0042", "vfd-42" or just "42".
 */
function normaliseAssetId(raw) {
  const text = raw.trim().toUpperCase();
  const digits = text.replace(/^VFD-?/, "");

  if (!/^\d+$/.test(digits)) {
    return "";
  }

  return `VFD-${digits.padStart(4, "0")}`;
}

export default function AssetFilters({
  band,
  onBandChange,
  bandCounts,
  onJump,
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState({
    busy: false,
    error: "",
  });

  async function handleSubmit(event) {
    event.preventDefault();

    const assetId = normaliseAssetId(query);

    if (!assetId) {
      setStatus({
        busy: false,
        error: "Use an id like VFD-0042.",
      });
      return;
    }

    setStatus({ busy: true, error: "" });

    const error = await onJump(assetId);

    setStatus({ busy: false, error });

    if (!error) {
      setQuery("");
    }
  }

  return (
    <div className="asset-filters">
      <div
        className="filter-chips"
        role="group"
        aria-label="Filter assets by risk band"
      >
        {BANDS.map((option) => {
          const count =
            option.value === "all"
              ? null
              : bandCounts?.[option.value] ?? 0;

          return (
            <button
              type="button"
              key={option.value}
              className={`filter-chip ${option.value} ${
                band === option.value ? "active" : ""
              }`}
              aria-pressed={band === option.value}
              onClick={() => onBandChange(option.value)}
            >
              {option.label}
              {count !== null && <small>{count}</small>}
            </button>
          );
        })}
      </div>

      <form className="asset-jump" onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          placeholder="Go to asset, e.g. VFD-0042"
          aria-label="Go to asset id"
          onChange={(event) => setQuery(event.target.value)}
        />

        <button type="submit" disabled={status.busy}>
          {status.busy ? "..." : "GO"}
        </button>
      </form>

      {status.error && (
        <p className="asset-jump-error" role="alert">
          {status.error}
        </p>
      )}
    </div>
  );
}
