import { useEffect, useRef, useState } from "react";

export default function DashboardHeader({
  apiStatus,
  theme,
  onThemeToggle,
  onLogout,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const profileRef = useRef(null);

  const isOnline = apiStatus === "ok";
  const isDarkTheme = theme === "dark";

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

    document.addEventListener(
      "mousedown",
      handleOutsideClick,
    );

    document.addEventListener(
      "keydown",
      handleEscape,
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleOutsideClick,
      );

      document.removeEventListener(
        "keydown",
        handleEscape,
      );
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
          className={`status-dot ${
            isOnline ? "online" : "offline"
          }`}
          title={
            isOnline
              ? "System online"
              : "System offline"
          }
          aria-label={
            isOnline
              ? "System online"
              : "System offline"
          }
        />

        <button
          type="button"
          className="theme-toggle-button"
          aria-label={
            isDarkTheme
              ? "Switch to light theme"
              : "Switch to dark theme"
          }
          title={
            isDarkTheme
              ? "Switch to light theme"
              : "Switch to dark theme"
          }
          onClick={onThemeToggle}
        >
          {isDarkTheme ? <SunIcon /> : <MoonIcon />}
        </button>

        <div
          className="profile-menu"
          ref={profileRef}
        >
          <button
            type="button"
            className="avatar avatar-button"
            aria-label="Open profile menu"
            aria-expanded={menuOpen}
            onClick={() =>
              setMenuOpen((current) => !current)
            }
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

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="17"
      height="17"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      />

      <path
        d="
          M12 2V4
          M12 20V22
          M4.93 4.93L6.34 6.34
          M17.66 17.66L19.07 19.07
          M2 12H4
          M20 12H22
          M4.93 19.07L6.34 17.66
          M17.66 6.34L19.07 4.93
        "
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="17"
      height="17"
      aria-hidden="true"
    >
      <path
        d="
          M20.2 15.2
          A8.5 8.5 0 0 1 8.8 3.8
          A8.5 8.5 0 1 0 20.2 15.2
        "
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}