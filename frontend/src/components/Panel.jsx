/*
 * Panels render only the actions they are given. The old per-panel menu button
 * had no menu behind it, so it has been removed rather than left as a dead
 * control.
 */
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

        {actions && (
          <div className="panel-actions">{actions}</div>
        )}
      </div>

      <div className="panel-content">{children}</div>
    </section>
  );
}
