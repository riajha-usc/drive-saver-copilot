function formatFailureMode(mode) {
  if (!mode || mode === "none") {
    return "No predicted failure";
  }

  return mode.replaceAll("_", " ").toUpperCase();
}

export default function AssetTable({
  assets,
  selectedAssetId,
  onSelect,
  loading,
  error,
}) {
  if (loading) {
    return <p className="asset-state">Loading assets...</p>;
  }

  if (error) {
    return <p className="asset-state error-text">{error}</p>;
  }

  if (assets.length === 0) {
    return <p className="asset-state">No assets found.</p>;
  }

  return (
    <div className="asset-table">
      {assets.map((asset) => (
        <button
          key={asset.asset_id}
          className={`asset-row ${
            selectedAssetId === asset.asset_id ? "selected" : ""
          }`}
          onClick={() => onSelect(asset.asset_id)}
        >
          <div className="asset-row-top">
            <strong>{asset.asset_id}</strong>

            <span className={`risk-badge ${asset.risk_band}`}>
              {asset.risk_band}
            </span>
          </div>

          <div className="asset-row-details">
            <span>
              Risk {(asset.failure_probability * 100).toFixed(1)}%
            </span>

            <span>RUL {asset.rul_hours.toFixed(1)}h</span>
          </div>

          <small>{formatFailureMode(asset.likely_failure_mode)}</small>
        </button>
      ))}
    </div>
  );
}