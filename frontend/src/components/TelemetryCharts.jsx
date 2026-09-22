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

  if (points.length === 0) {
    return (
      <div className="telemetry-state">No telemetry history available.</div>
    );
  }

  return (
    <div className="telemetry-charts">
      <ChartCard title="TEMPERATURE" unit="K">
        <LineChart data={points}>
          <ChartBase />

          <Line
            type="monotone"
            dataKey="air_temperature"
            name="Air temperature"
            stroke="#bdbdbd"
            strokeWidth={2}
            dot={false}
          />

          <Line
            type="monotone"
            dataKey="process_temperature"
            name="Process temperature"
            stroke="#ff4d40"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ChartCard>

      <ChartCard title="ROTATIONAL SPEED" unit="RPM">
        <LineChart data={points}>
          <ChartBase />

          <Line
            type="monotone"
            dataKey="rotational_speed"
            name="Speed"
            stroke="#ff4d40"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ChartCard>

      <ChartCard title="TORQUE" unit="Nm">
        <LineChart data={points}>
          <ChartBase />

          <Line
            type="monotone"
            dataKey="torque"
            name="Torque"
            stroke="#f5a623"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ChartCard>

      {note && <p className="telemetry-note">{note}</p>}
    </div>
  );
}

function ChartCard({ title, unit, children }) {
  return (
    <div className="telemetry-chart-card">
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

      <Tooltip contentStyle={tooltipStyle} />

      <Legend
        wrapperStyle={{
          color: "#bdbdbd",
          fontSize: "11px",
        }}
      />
    </>
  );
}