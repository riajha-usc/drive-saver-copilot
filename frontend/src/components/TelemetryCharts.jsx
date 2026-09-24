import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/*
 * Recharts draws SVG with explicit colours, so the palette follows the
 * dashboard theme here rather than through CSS.
 */
const PALETTES = {
  dark: {
    grid: "#343434",
    axis: "#777",
    tick: "#888",
    tooltipBackground: "#171717",
    tooltipBorder: "#444",
    tooltipText: "#f2f2f2",
    muted: "#bdbdbd",
    primary: "#ff4d40",
    torque: "#f5a623",
  },
  light: {
    grid: "#e3e6ea",
    axis: "#9aa3ad",
    tick: "#69727d",
    tooltipBackground: "#ffffff",
    tooltipBorder: "#d9dee5",
    tooltipText: "#20242a",
    muted: "#5b6570",
    primary: "#e53935",
    torque: "#a96800",
  },
};

export default function TelemetryCharts({
  points,
  note,
  loading,
  error,
  hasSelection,
  theme = "dark",
}) {
  const [expandedChart, setExpandedChart] = useState(null);
  const palette = PALETTES[theme] ?? PALETTES.dark;

  if (!hasSelection) {
    return (
      <div className="telemetry-state">
        Select an asset to view telemetry.
      </div>
    );
  }

  if (loading) {
    return <div className="telemetry-state">Loading telemetry...</div>;
  }

  if (error) {
    return <div className="telemetry-state error-text">{error}</div>;
  }

  if (!points || points.length === 0) {
    return (
      <div className="telemetry-state">
        No telemetry history available.
      </div>
    );
  }

  function toggleChart(chartName) {
    setExpandedChart((currentChart) =>
      currentChart === chartName ? null : chartName
    );
  }

  function handleKeyboard(event, chartName) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleChart(chartName);
    }
  }

  const showTemperature =
    expandedChart === null || expandedChart === "temperature";

  const showSpeed =
    expandedChart === null || expandedChart === "speed";

  const showTorque =
    expandedChart === null || expandedChart === "torque";

  return (
    <div
      className={`telemetry-charts ${
        expandedChart ? "telemetry-charts-expanded" : ""
      }`}
    >
      {showTemperature && (
        <ChartCard
          title="TEMPERATURE"
          unit="K"
          expanded={expandedChart === "temperature"}
          onClick={() => toggleChart("temperature")}
          onKeyDown={(event) => handleKeyboard(event, "temperature")}
        >
          <LineChart data={points}>
            <ChartBase palette={palette} />

            <Line
              type="monotone"
              dataKey="air_temperature"
              name="Air temperature"
              stroke={palette.muted}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />

            <Line
              type="monotone"
              dataKey="process_temperature"
              name="Process temperature"
              stroke={palette.primary}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ChartCard>
      )}

      {showSpeed && (
        <ChartCard
          title="ROTATIONAL SPEED"
          unit="RPM"
          expanded={expandedChart === "speed"}
          onClick={() => toggleChart("speed")}
          onKeyDown={(event) => handleKeyboard(event, "speed")}
        >
          <LineChart data={points}>
            <ChartBase palette={palette} />

            <Line
              type="monotone"
              dataKey="rotational_speed"
              name="Speed"
              stroke={palette.primary}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ChartCard>
      )}

      {showTorque && (
        <ChartCard
          title="TORQUE"
          unit="Nm"
          expanded={expandedChart === "torque"}
          onClick={() => toggleChart("torque")}
          onKeyDown={(event) => handleKeyboard(event, "torque")}
        >
          <LineChart data={points}>
            <ChartBase palette={palette} />

            <Line
              type="monotone"
              dataKey="torque"
              name="Torque"
              stroke={palette.torque}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ChartCard>
      )}

      {note && <p className="telemetry-note">{note}</p>}
    </div>
  );
}

function ChartCard({
  title,
  unit,
  expanded,
  onClick,
  onKeyDown,
  children,
}) {
  return (
    <div
      className={`telemetry-chart-card ${
        expanded ? "telemetry-chart-card-expanded" : ""
      }`}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      aria-label={`${expanded ? "Collapse" : "Expand"} ${title} chart`}
      onClick={onClick}
      onKeyDown={onKeyDown}
    >
      <div className="telemetry-chart-title">
        <strong>{title}</strong>
        <span>{unit}</span>
      </div>

      <div className="telemetry-chart-area">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>

    </div>
  );
}

function ChartBase({ palette }) {
  return (
    <>
      <CartesianGrid stroke={palette.grid} strokeDasharray="3 3" />

      <XAxis
        dataKey="row_index"
        stroke={palette.axis}
        tick={{ fill: palette.tick, fontSize: 10 }}
        tickLine={false}
      />

      {/*
        Fit the axis to the data. Starting at zero flattened the temperature
        lines, which sit between roughly 295 and 315 K, into one straight line
        along the top of the chart.
      */}
      <YAxis
        width={45}
        domain={["auto", "auto"]}
        allowDecimals={false}
        stroke={palette.axis}
        tick={{ fill: palette.tick, fontSize: 10 }}
        tickLine={false}
      />

      <Tooltip
        contentStyle={{
          background: palette.tooltipBackground,
          border: `1px solid ${palette.tooltipBorder}`,
          borderRadius: "8px",
          color: palette.tooltipText,
        }}
        labelStyle={{ color: palette.muted }}
      />

      <Legend
        wrapperStyle={{
          color: palette.muted,
          fontSize: "11px",
        }}
      />
    </>
  );
}