import { useEffect, useState } from "react";

/*
 * The planned maintenance window is the operator's input to the decision.
 * The agent looks for the smallest adjustment that carries the asset to this
 * point, so a 24 hour window and a one week window are different questions.
 *
 * The API accepts more than 0 and at most 2000 hours.
 */
const PRESETS = [
  { hours: 24, label: "24h" },
  { hours: 48, label: "48h" },
  { hours: 72, label: "72h" },
  { hours: 168, label: "1 wk" },
];

const MIN_HOURS = 1;
const MAX_HOURS = 2000;

export default function MaintenanceWindowControl({
  value,
  onChange,
  disabled = false,
}) {
  const [draft, setDraft] = useState(String(value));
  const [invalid, setInvalid] = useState(false);

  /*
   * Keep the text box in step when a preset changes the value.
   */
  useEffect(() => {
    setDraft(String(value));
    setInvalid(false);
  }, [value]);

  function commit() {
    const hours = Number(draft);

    if (
      !Number.isFinite(hours) ||
      hours < MIN_HOURS ||
      hours > MAX_HOURS
    ) {
      setInvalid(true);
      return;
    }

    setInvalid(false);

    const rounded = Math.round(hours);

    if (rounded !== value) {
      onChange(rounded);
    } else {
      setDraft(String(rounded));
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    }

    if (event.key === "Escape") {
      setDraft(String(value));
      setInvalid(false);
    }
  }

  return (
    <div className="window-control">
      <div className="window-control-label">
        <span>PLANNED MAINTENANCE WINDOW</span>
        <small>
          The agent finds the smallest change that reaches it
        </small>
      </div>

      <div className="window-control-inputs">
        <div
          className="window-presets"
          role="group"
          aria-label="Maintenance window presets"
        >
          {PRESETS.map((preset) => (
            <button
              type="button"
              key={preset.hours}
              className={`window-preset ${
                value === preset.hours ? "active" : ""
              }`}
              aria-pressed={value === preset.hours}
              disabled={disabled}
              onClick={() => onChange(preset.hours)}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <label
          className={`window-input ${invalid ? "invalid" : ""}`}
        >
          <input
            type="number"
            inputMode="numeric"
            min={MIN_HOURS}
            max={MAX_HOURS}
            step="1"
            value={draft}
            disabled={disabled}
            aria-label="Maintenance window in hours"
            aria-invalid={invalid}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={handleKeyDown}
          />
          <span>hours</span>
        </label>
      </div>

      {invalid && (
        <p className="window-error" role="alert">
          Enter a whole number of hours from {MIN_HOURS} to{" "}
          {MAX_HOURS}.
        </p>
      )}
    </div>
  );
}
