import React, { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
} from "recharts";
import {
  Activity,
  Cpu,
  Database,
  Pause,
  Play,
  RotateCcw,
  Settings,
  TrendingUp,
  Zap,
} from "lucide-react";

const QuantumDiscoveryLab = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [iteration, setIteration] = useState(0);
  const [fidelityData, setFidelityData] = useState([]);
  const [currentFidelity, setCurrentFidelity] = useState(0.3);
  const [noiseLevel, setNoiseLevel] = useState(0.05);
  const [shots, setShots] = useState(500);
  const [numQubits, setNumQubits] = useState(4);
  const [bestConfig, setBestConfig] = useState({ fidelity: 0, iteration: 0, theta: 0 });
  const [circuitParams, setCircuitParams] = useState({ theta: 1.5, phi: 0.8, lambda: 0.5 });
  const [logs, setLogs] = useState([]);
  const [backend, setBackend] = useState("simulator");
  const [convergenceRate, setConvergenceRate] = useState(0);
  const maxIterations = 100;
  const runLogEndpoint = import.meta.env.VITE_RUN_LOG_ENDPOINT || "";

  const getSessionId = () => {
    const key = "synqubi_session_id";
    const existing = localStorage.getItem(key);
    if (existing) return existing;
    const created = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    localStorage.setItem(key, created);
    return created;
  };

  const storeRunLocal = (payload) => {
    const key = "synqubi_run_logs";
    const existing = JSON.parse(localStorage.getItem(key) || "[]");
    const next = [payload, ...existing].slice(0, 100);
    localStorage.setItem(key, JSON.stringify(next));
  };

  const trackRun = (payload) => {
    const enriched = { ...payload, sessionId: getSessionId() };
    storeRunLocal(enriched);

    if (!runLogEndpoint) {
      return;
    }

    const body = JSON.stringify(enriched);
    if (navigator.sendBeacon) {
      navigator.sendBeacon(runLogEndpoint, body);
      return;
    }

    fetch(runLogEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  };

  const simulateQuantumCircuit = async (params, noise, depth, numShots) => {
    const idealEnergy = Math.cos(params.theta);
    const bitFlipNoise = noise * (Math.random() - 0.5) * 2;
    const shotNoise = (1 / Math.sqrt(numShots)) * (Math.random() - 0.5);
    const depthPenalty = Math.exp(-0.05 * depth);

    const measuredEnergy = idealEnergy + bitFlipNoise + shotNoise;
    const fidelity = (1 + measuredEnergy * depthPenalty) / 2;

    await new Promise((resolve) => setTimeout(resolve, 50));

    return {
      energy: measuredEnergy,
      fidelity: Math.max(0, Math.min(1, fidelity)),
      params,
    };
  };

  const spsaOptimize = async (currentParams, iter) => {
    const a = 0.6;
    const c = 0.2;
    const alpha = 0.602;
    const gamma = 0.101;

    const ak = a / Math.pow(iter + 1, alpha);
    const ck = c / Math.pow(iter + 1, gamma);

    const delta = Math.random() > 0.5 ? 1 : -1;

    const thetaPlus = currentParams.theta + ck * delta;
    const thetaMinus = currentParams.theta - ck * delta;

    const resultPlus = await simulateQuantumCircuit(
      { ...currentParams, theta: thetaPlus },
      noiseLevel,
      numQubits,
      shots
    );

    const resultMinus = await simulateQuantumCircuit(
      { ...currentParams, theta: thetaMinus },
      noiseLevel,
      numQubits,
      shots
    );

    const gradient = (resultPlus.energy - resultMinus.energy) / (2 * ck * delta);

    let newTheta = currentParams.theta - ak * gradient;
    newTheta = Math.max(0, Math.min(2 * Math.PI, newTheta));

    return {
      theta: newTheta,
      phi: currentParams.phi,
      lambda: currentParams.lambda,
      energy: resultPlus.energy,
      fidelity: resultPlus.fidelity,
    };
  };

  const addLog = (message, type = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) =>
      [
        {
          id: Date.now(),
          message,
          timestamp,
          type,
        },
        ...prev,
      ].slice(0, 10)
    );
  };

  const runOptimizationStep = async () => {
    try {
      const result = await spsaOptimize(circuitParams, iteration);

      setCircuitParams({
        theta: result.theta,
        phi: result.phi,
        lambda: result.lambda,
      });

      setCurrentFidelity(result.fidelity);

      if (fidelityData.length > 0) {
        const lastFidelity = fidelityData[fidelityData.length - 1].fidelity;
        const rate = ((result.fidelity - lastFidelity / 100) / lastFidelity) * 100;
        setConvergenceRate(rate);
      }

      if (result.fidelity > bestConfig.fidelity) {
        setBestConfig({
          fidelity: result.fidelity,
          iteration: iteration + 1,
          theta: result.theta,
        });
        addLog(
          `New best! Fidelity: ${(result.fidelity * 100).toFixed(2)}%, θ=${result.theta.toFixed(4)}`,
          "success"
        );
      }

      setFidelityData((prev) =>
        [
          ...prev,
          {
            iteration: iteration + 1,
            fidelity: result.fidelity * 100,
            energy: result.energy,
            noise: noiseLevel * 100,
            theta: result.theta,
            phi: result.phi,
            lambda: result.lambda,
            target: 95,
          },
        ].slice(-50)
      );

      if ((iteration + 1) % 10 === 0) {
        addLog(
          `Step ${iteration + 1}: E=${result.energy.toFixed(4)}, F=${(result.fidelity * 100).toFixed(2)}%`,
          "info"
        );
      }
    } catch (error) {
      addLog(`Error in step ${iteration + 1}: ${error.message}`, "error");
    }
  };

  useEffect(() => {
    if (isRunning && iteration < maxIterations) {
      runOptimizationStep().then(() => {
        setIteration((prev) => prev + 1);
      });
    } else if (iteration >= maxIterations && isRunning) {
      setIsRunning(false);
      const optimalTheta = Math.PI;
      const foundTheta = bestConfig.theta;
      const error = Math.abs(foundTheta - optimalTheta);
      addLog(
        `Optimization complete! Converged to θ=${foundTheta.toFixed(4)} (optimal: π=${optimalTheta.toFixed(4)}, error: ${error.toFixed(4)})`,
        "success"
      );
    }
  }, [isRunning, iteration]);

  const handleReset = () => {
    setIsRunning(false);
    setIteration(0);
    setFidelityData([]);
    setCurrentFidelity(0.3);
    setCircuitParams({ theta: 1.5, phi: 0.8, lambda: 0.5 });
    setBestConfig({ fidelity: 0, iteration: 0, theta: 0 });
    setLogs([]);
    setConvergenceRate(0);
    addLog("System reset - Ready for new optimization run", "info");
  };

  const handleStart = () => {
    if (iteration === 0) {
      addLog(
        `Starting SPSA optimization with ${numQubits} qubits, ${shots} shots, ${(noiseLevel * 100).toFixed(1)}% noise`,
        "info"
      );
      addLog(
        `Backend: ${backend === "qiskit" ? "Qiskit Aer Simulator" : "Custom Quantum Simulator"}`,
        "info"
      );
    }
    if (!isRunning) {
      trackRun({
        event: "run_clicked",
        timestamp: new Date().toISOString(),
        backend,
        numQubits,
        shots,
        noiseLevel,
        theta: circuitParams.theta,
        phi: circuitParams.phi,
        lambda: circuitParams.lambda,
      });
    }
    setIsRunning(!isRunning);
  };

  const QuantumGate = ({ label, active, angle }) => (
    <div className="relative">
      <div
        className={`w-16 h-16 rounded-lg flex items-center justify-center font-mono text-sm transition-all duration-300 ${
          active
            ? "bg-blue-500 text-white shadow-lg shadow-blue-500/50 scale-110"
            : "bg-gray-700 text-gray-300"
        }`}
      >
        {label}
      </div>
      {angle !== undefined && (
        <div className="absolute -bottom-6 left-0 right-0 text-center text-xs text-gray-400 font-mono">
          {angle.toFixed(2)}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-6">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            SynQubi
          </h1>
          <p className="text-gray-400">Autonomous Quantum Discovery Lab</p>
          <div className="flex items-center justify-center gap-4 mt-3 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Database className="w-4 h-4" />
              Diachronic Memory
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="w-4 h-4" />
              {backend === "qiskit" ? "Qiskit Aer" : "Native Simulator"}
            </span>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
          <div className="flex items-center gap-2 mb-3">
            <Settings className="w-5 h-5 text-gray-400" />
            <h3 className="text-lg font-semibold">Experiment Configuration</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Qubits</label>
              <select
                value={numQubits}
                onChange={(e) => setNumQubits(Number(e.target.value))}
                disabled={isRunning}
                className="w-full bg-gray-700 rounded px-3 py-2 text-white disabled:opacity-50"
              >
                <option value={2}>2 Qubits</option>
                <option value={3}>3 Qubits</option>
                <option value={4}>4 Qubits</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Shots</label>
              <select
                value={shots}
                onChange={(e) => setShots(Number(e.target.value))}
                disabled={isRunning}
                className="w-full bg-gray-700 rounded px-3 py-2 text-white disabled:opacity-50"
              >
                <option value={100}>100</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Noise Level</label>
              <select
                value={noiseLevel}
                onChange={(e) => setNoiseLevel(Number(e.target.value))}
                disabled={isRunning}
                className="w-full bg-gray-700 rounded px-3 py-2 text-white disabled:opacity-50"
              >
                <option value={0.01}>1% (Low)</option>
                <option value={0.05}>5% (Medium)</option>
                <option value={0.1}>10% (High)</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Backend</label>
              <select
                value={backend}
                onChange={(e) => setBackend(e.target.value)}
                disabled={isRunning}
                className="w-full bg-gray-700 rounded px-3 py-2 text-white disabled:opacity-50"
              >
                <option value="simulator">Simulator</option>
                <option value="qiskit">Qiskit Aer</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-5 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold flex items-center gap-2 text-gray-400">
                <Zap className="w-4 h-4 text-yellow-400" />
                Iteration
              </h3>
              <span className="text-2xl font-mono text-blue-400">
                {iteration}/{maxIterations}
              </span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(iteration / maxIterations) * 100}%` }}
              />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-5 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold flex items-center gap-2 text-gray-400">
                <Activity className="w-4 h-4 text-green-400" />
                Fidelity
              </h3>
              <span className="text-2xl font-mono text-green-400">
                {(currentFidelity * 100).toFixed(1)}%
              </span>
            </div>
            <div className="text-xs text-gray-500">
              Convergence: {convergenceRate > 0 ? "+" : ""}
              {convergenceRate.toFixed(2)}%
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-5 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold flex items-center gap-2 text-gray-400">
                <TrendingUp className="w-4 h-4 text-purple-400" />
                Best Result
              </h3>
              <span className="text-2xl font-mono text-purple-400">
                {(bestConfig.fidelity * 100).toFixed(1)}%
              </span>
            </div>
            <div className="text-xs text-gray-500">@ Step {bestConfig.iteration}</div>
          </div>

          <div className="bg-gray-800 rounded-lg p-5 border border-gray-700">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-gray-400 mb-1">θ Parameter</h3>
              <span className="text-2xl font-mono text-orange-400">
                {circuitParams.theta.toFixed(4)}
              </span>
            </div>
            <div className="text-xs text-gray-500">Target: π ≈ 3.1416</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-semibold mb-5">Quantum Circuit ({numQubits} Qubits)</h3>
            <div className="space-y-5">
              {Array.from({ length: numQubits }).map((_, qubit) => (
                <div key={qubit} className="flex items-center gap-3">
                  <div className="w-12 text-gray-400 font-mono text-sm">|q{qubit}⟩</div>
                  <div className="flex gap-2 flex-1">
                    <QuantumGate label="H" active={isRunning && iteration % numQubits === qubit} />
                    <QuantumGate
                      label="Ry"
                      active={isRunning && iteration % numQubits === qubit}
                      angle={qubit === 0 ? circuitParams.theta : circuitParams.phi}
                    />
                    <QuantumGate
                      label="Rz"
                      active={isRunning && iteration % numQubits === qubit}
                      angle={circuitParams.lambda}
                    />
                    {qubit < numQubits - 1 && (
                      <QuantumGate label="CX" active={isRunning && iteration % numQubits === qubit} />
                    )}
                  </div>
                  <div className="w-12 h-12 rounded-lg bg-gray-700 flex items-center justify-center">
                    <div
                      className={`w-3 h-3 rounded-full transition-all ${
                        isRunning ? "bg-green-400 animate-pulse" : "bg-gray-500"
                      }`}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-semibold mb-4">Fidelity Convergence (SPSA)</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={fidelityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="iteration" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1F2937",
                    border: "1px solid #374151",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#9CA3AF" }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="fidelity"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  dot={false}
                  name="Fidelity %"
                />
                <Line
                  type="monotone"
                  dataKey="target"
                  stroke="#10B981"
                  strokeWidth={1.5}
                  strokeDasharray="5 5"
                  dot={false}
                  name="Target %"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-semibold mb-4">Parameter Space Exploration (3D)</h3>
            <div className="h-[300px]">
              <Plot
                data={[
                  {
                    type: "scatter3d",
                    mode: "markers",
                    x: fidelityData.map((d) => d.theta),
                    y: fidelityData.map((d) => d.energy),
                    z: fidelityData.map((d) => d.fidelity),
                    marker: {
                      size: 4,
                      color: fidelityData.map((d) => d.fidelity),
                      colorscale: "Viridis",
                      opacity: 0.8,
                    },
                  },
                ]}
                layout={{
                  autosize: true,
                  paper_bgcolor: "transparent",
                  plot_bgcolor: "transparent",
                  margin: { l: 0, r: 0, t: 0, b: 0 },
                  scene: {
                    xaxis: { title: "θ", color: "#9CA3AF" },
                    yaxis: { title: "Energy", color: "#9CA3AF" },
                    zaxis: { title: "Fidelity %", color: "#9CA3AF" },
                    bgcolor: "rgba(0,0,0,0)",
                  },
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%", height: "100%" }}
              />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-semibold mb-4">Diachronic Discovery Log</h3>
            <div className="space-y-2 font-mono text-xs max-h-64 overflow-y-auto">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className={`flex gap-2 ${
                    log.type === "success"
                      ? "text-green-400"
                      : log.type === "error"
                      ? "text-red-400"
                      : "text-gray-400"
                  }`}
                >
                  <span className="text-gray-600">[{log.timestamp}]</span>
                  <span className="flex-1">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-4 justify-center items-center">
          <button
            onClick={handleStart}
            disabled={iteration >= maxIterations}
            className={`px-8 py-4 rounded-lg font-semibold flex items-center gap-2 transition-all ${
              isRunning
                ? "bg-yellow-500 hover:bg-yellow-600 text-gray-900"
                : iteration >= maxIterations
                ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                : "bg-blue-500 hover:bg-blue-600 text-white shadow-lg shadow-blue-500/30"
            }`}
          >
            {isRunning ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            {isRunning
              ? "Pause"
              : iteration === 0
              ? "Start Discovery"
              : iteration >= maxIterations
              ? "Complete"
              : "Resume"}
          </button>
          <button
            onClick={handleReset}
            className="px-8 py-4 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold flex items-center gap-2 transition-all"
          >
            <RotateCcw className="w-5 h-5" />
            Reset
          </button>
        </div>

        <div className="mt-8 text-center space-y-1">
          <p className="text-gray-500 text-sm">
            Autonomous loop: Propose → Execute → Measure → Learn → Optimize
          </p>
          <p className="text-gray-600 text-xs">
            SPSA optimization | Qiskit-compatible backend | Diachronic memory | Bit-flip noise model
          </p>
          <p className="text-gray-700 text-xs mt-2">
            Based on: <code className="bg-gray-800 px-2 py-1 rounded">autonomous_quantum_lab.py</code>
          </p>
        </div>
      </div>
    </div>
  );
};

export default QuantumDiscoveryLab;
