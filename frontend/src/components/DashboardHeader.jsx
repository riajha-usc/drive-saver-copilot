/*
 * There is no sign-in in this prototype, so the header carries no profile or
 * log out control. A control that does nothing reads as broken in a demo.
 *
 * The left mark names the challenge rather than using ABB's logo as the
 * product's own brand.
 */
export default function DashboardHeader({
  apiStatus,
  theme,
  onThemeToggle,
}) {
  const isOnline = apiStatus === "ok";
  const isDarkTheme = theme === "dark";

  return (
    <header className="dashboard-header">
      <div className="header-context">
        <strong>DSC</strong>
        <span>ABB Accelerator 2026 prototype</span>
      </div>

      <h1>DRIVE-SAVER COPILOT</h1>

      <div className="header-actions">
        <span
          className={`status-dot ${
            isOnline ? "online" : "offline"
          }`}
          role="status"
          title={
            isOnline
              ? "API online"
              : "API offline"
          }
          aria-label={
            isOnline
              ? "API online"
              : "API offline"
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