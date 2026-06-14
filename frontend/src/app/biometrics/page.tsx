"use client";
import { useState, useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, Legend, RadialBarChart, RadialBar } from "recharts";

// ─── Generate realistic human sensor data ───
function genHumanSensor(n = 100) {
  return Array.from({ length: n }, (_, i) => ({
    t: i * 20, // ms
    acc_x: 0.5 * Math.sin(i / 5 + Math.random()) + (Math.random() - 0.5) * 0.6,
    acc_y: 0.3 * Math.sin(i / 7 + 1.2) + (Math.random() - 0.5) * 0.5,
    acc_z: 9.81 + (Math.random() - 0.5) * 0.8,
    gyro_x: (Math.random() - 0.5) * 0.3,
    gyro_y: (Math.random() - 0.5) * 0.25,
    gyro_z: (Math.random() - 0.5) * 0.2,
  }));
}

function genRATSensor(n = 100) {
  return Array.from({ length: n }, (_, i) => ({
    t: i * 20,
    acc_x: 2.0 * Math.sin(i * 0.628),
    acc_y: 1.5 * Math.sin(i * 0.628 + 0.5),
    acc_z: 0.1,
    gyro_x: 0.001,
    gyro_y: 0.001,
    gyro_z: 0.0,
  }));
}

const CHANNELS = [
  { key: "acc_x", color: "#00FFD1", label: "Acc X" },
  { key: "acc_y", color: "#7B61FF", label: "Acc Y" },
  { key: "acc_z", color: "#FF6B35", label: "Acc Z" },
  { key: "gyro_x", color: "#FFD700", label: "Gyro X" },
  { key: "gyro_y", color: "#FF3CAC", label: "Gyro Y" },
  { key: "gyro_z", color: "#00C9FF", label: "Gyro Z" },
];

// ─── Keystroke density mock data ───
function genKeystrokeData() {
  return {
    human: Array.from({ length: 30 }, () => ({
      dwell: 50 + Math.random() * 150,
      flight: 80 + Math.random() * 320,
    })),
    bot: Array.from({ length: 30 }, () => ({
      dwell: 100 + Math.random() * 5,
      flight: 150 + Math.random() * 3,
    })),
  };
}

export default function BiometricsPage() {
  const [mode, setMode] = useState<"human" | "rat">("human");
  const sensorData = useMemo(() => mode === "human" ? genHumanSensor() : genRATSensor(), [mode]);
  const keystroke = useMemo(genKeystrokeData, []);

  const entropy = mode === "human" ? 3.42 : 1.18;
  const pinnScore = mode === "human" ? 0.91 : 0.12;
  const isHuman = mode === "human";

  const entropyGauge = [{ name: "Entropy", value: entropy, fill: entropy > 1.4 ? "#00FFD1" : "#FF3CAC" }];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-extrabold">Biometrics <span className="text-kx-gold">Monitor</span></h1>
          <div className="text-xs text-kx-muted">PINN sensor analysis, keystroke dynamics, entropy scoring</div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setMode("human")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold border transition-all ${mode === "human" ? 'border-kx-teal bg-[#00FFD115] text-kx-teal' : 'border-kx-border text-kx-muted'}`}>
            👤 Human Session
          </button>
          <button onClick={() => setMode("rat")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold border transition-all ${mode === "rat" ? 'border-[#FF3CAC] bg-[#FF3CAC15] text-[#FF3CAC]' : 'border-kx-border text-kx-muted'}`}>
            🤖 RAT Session
          </button>
        </div>
      </div>

      {/* Score Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className={`glass-card p-4 ${isHuman ? 'glow-teal' : 'glow-pink'}`}>
          <div className="text-xs text-kx-muted mb-1">PINN Score</div>
          <div className="text-3xl font-extrabold font-mono" style={{ color: isHuman ? '#00FFD1' : '#FF3CAC' }}>
            {pinnScore.toFixed(3)}
          </div>
          <div className="text-xs mt-1" style={{ color: isHuman ? '#00FFD1' : '#FF3CAC' }}>
            {isHuman ? "✓ Human Detected" : "✗ Synthetic Detected"}
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="text-xs text-kx-muted mb-1">Shannon Entropy</div>
          <div className="text-3xl font-extrabold font-mono" style={{ color: entropy > 1.4 ? '#00FFD1' : '#FF3CAC' }}>
            {entropy.toFixed(2)} <span className="text-sm">bits</span>
          </div>
          <div className="text-xs text-kx-muted mt-1">Threshold: 1.40 bits</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-xs text-kx-muted mb-1">Gravity Alignment</div>
          <div className="text-3xl font-extrabold font-mono" style={{ color: isHuman ? '#00FFD1' : '#FF6B35' }}>
            {isHuman ? "0.04" : "0.72"}
          </div>
          <div className="text-xs text-kx-muted mt-1">Deviation from g·cos(θ)</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-xs text-kx-muted mb-1">Keystroke GMM</div>
          <div className="text-3xl font-extrabold font-mono" style={{ color: isHuman ? '#FFD700' : '#FF3CAC' }}>
            {isHuman ? "0.87" : "0.09"}
          </div>
          <div className="text-xs text-kx-muted mt-1">K=3 Gaussian Mixture</div>
        </div>
      </div>

      {/* Sensor Time Series */}
      <div className="glass-card p-5">
        <div className="text-sm font-bold text-kx-head mb-4">6-Channel IMU Sensor Stream</div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sensorData}>
              <XAxis dataKey="t" stroke="#4A6880" fontSize={10} />
              <YAxis stroke="#4A6880" fontSize={10} />
              <Tooltip contentStyle={{ background: '#07111F', border: '1px solid #0F2035', borderRadius: 8, fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {CHANNELS.map(ch => (
                <Line key={ch.key} type="monotone" dataKey={ch.key} stroke={ch.color}
                  strokeWidth={1.5} dot={false} name={ch.label} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Keystroke Density */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="glass-card p-5">
          <div className="text-sm font-bold text-kx-head mb-3">Keystroke Timing — Human</div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={keystroke.human}>
                <XAxis dataKey="dwell" stroke="#4A6880" fontSize={10} label={{ value: 'Dwell (ms)', fontSize: 10, fill: '#4A6880' }} />
                <YAxis stroke="#4A6880" fontSize={10} />
                <Tooltip contentStyle={{ background: '#07111F', border: '1px solid #0F2035', borderRadius: 8, fontSize: 11 }} />
                <Line type="monotone" dataKey="flight" stroke="#00FFD1" strokeWidth={2} dot={{ r: 3, fill: '#00FFD1' }} name="Flight (ms)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="text-[10px] text-kx-muted mt-2">High variance = natural human typing pattern</div>
        </div>
        <div className="glass-card p-5">
          <div className="text-sm font-bold text-kx-head mb-3">Keystroke Timing — Bot/RAT</div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={keystroke.bot}>
                <XAxis dataKey="dwell" stroke="#4A6880" fontSize={10} label={{ value: 'Dwell (ms)', fontSize: 10, fill: '#4A6880' }} />
                <YAxis stroke="#4A6880" fontSize={10} />
                <Tooltip contentStyle={{ background: '#07111F', border: '1px solid #0F2035', borderRadius: 8, fontSize: 11 }} />
                <Line type="monotone" dataKey="flight" stroke="#FF3CAC" strokeWidth={2} dot={{ r: 3, fill: '#FF3CAC' }} name="Flight (ms)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="text-[10px] text-kx-muted mt-2">Low variance = scripted/automated input pattern</div>
        </div>
      </div>
    </div>
  );
}
