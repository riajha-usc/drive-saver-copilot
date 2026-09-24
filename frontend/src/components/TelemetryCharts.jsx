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

const tooltipStyle = {
  background: "#171717",
  border: "1px solid #444",
  borderRadius: "8px",
  color: "#f2f2f2",
};

export default function TelemetryCharts({
  points,
  note,
  loading,
  error,
  hasSelection,
}) {
  const [expandedChart, setExpandedChart] = useState(null);

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
            <ChartBase />

            <Line
              type="monotone"
              dataKey="air_temperature"
              name="Air temperature"
              stroke="#bdbdbd"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />

            <Line
              type="monotone"
              dataKey="process_temperature"
              name="Process temperature"
              stroke="#ff4d40"
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
            <ChartBase />

            <Line
              type="monotone"
              dataKey="rotational_speed"
              name="Speed"
              stroke="#ff4d40"
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
            <ChartBase />

            <Line
              type="monotone"
              dataKey="torque"
              name="Torque"
              stroke="#f5a623"
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

function ChartBase() {
  return (
    <>
      <CartesianGrid stroke="#343434" strokeDasharray="3 3" />

      <XAxis
        dataKey="row_index"
        stroke="#777"
        tick={{ fill: "#888", fontSize: 10 }}
        tickLine={false}
      />

      <YAxis
        width={45}
        stroke="#777"
        tick={{ fill: "#888", fontSize: 10 }}
        tickLine={false}
      />

      <Tooltip
        contentStyle={tooltipStyle}
        labelStyle={{ color: "#bdbdbd" }}
      />

      <Legend
        wrapperStyle={{
          color: "#bdbdbd",
          fontSize: "11px",
        }}
      />
    </>
  );
}