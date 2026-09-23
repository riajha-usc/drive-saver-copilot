export default function Panel({
  title,
  children,
  className = "",
  actions,
}) {
  return (
    <section className={`dashboard-panel ${className}`}>
      <div className="panel-header">
        <h2>{title}</h2>

        <div className="panel-actions">
          {actions}
          <button className="menu-button" aria-label={`More options for ${title}`}>
          </button>
        </div>
      </div>

      <div className="panel-content">{children}</div>
    </section>
  );
}