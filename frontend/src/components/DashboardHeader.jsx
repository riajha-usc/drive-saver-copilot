import { useEffect, useRef, useState } from "react";

export default function DashboardHeader({ apiStatus, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const profileRef = useRef(null);

  const isOnline = apiStatus === "ok";

  useEffect(() => {
    function handleOutsideClick(event) {
      if (
        profileRef.current &&
        !profileRef.current.contains(event.target)
      ) {
        setMenuOpen(false);
      }
    }

    function handleEscape(event) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  function handleLogout() {
    setMenuOpen(false);

    if (onLogout) {
      onLogout();
    }
  }

  return (
    <header className="dashboard-header">
      <div className="abb-logo">ABB</div>

      <h1>DRIVE-SAVER COPILOT</h1>

      <div className="header-actions">
        <span
          className={`status-dot ${isOnline ? "online" : "offline"}`}
          title={isOnline ? "System online" : "System offline"}
          aria-label={isOnline ? "System online" : "System offline"}
        />

        <div className="profile-menu" ref={profileRef}>
          <button
            type="button"
            className="avatar avatar-button"
            aria-label="Open profile menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((current) => !current)}
          >
            SN
          </button>

          {menuOpen && (
            <div className="profile-dropdown">
              <div className="profile-details">
                <strong>Sharayu Nagre</strong>
                <span>Drive-Saver Dashboard</span>
              </div>

              <button
                type="button"
                className="logout-button"
                onClick={handleLogout}
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}