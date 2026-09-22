export default function DashboardHeader({ apiStatus }) {
  const isOnline = apiStatus === "ok";

  return (
    <header className="dashboard-header">
      <div className="abb-logo">ABB</div>

      <h1>DRIVE-SAVER COPILOT</h1>

      <div className="header-actions">
        <div className="system-status">
          <span className={`status-dot ${isOnline ? "online" : "offline"}`} />
          {isOnline ? "System Online" : "Connecting"}
        </div>

        <button className="icon-button" aria-label="Notifications">
          ♢
        </button>

        <div className="avatar">SN</div>
      </div>
    </header>
  );
}