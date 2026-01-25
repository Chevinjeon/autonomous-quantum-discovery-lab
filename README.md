# SynQubi

SynQubi is an autonomous quantum discovery lab MVP. This repo demonstrates a closed-loop
experiment system that proposes circuit parameters, runs noisy measurements on
a simulator, logs diachronic history, and optimizes toward lower energy.

## What’s included
- A library-free quantum simulator for a 1-qubit `Ry(theta)|0>` circuit
- Bit-flip noise + finite-shot sampling
- Diachronic memory (lab notebook) with best/last/diff helpers
- Brute-force grid search optimizer
- SPSA optimizer (robust under noise)
- Deterministic, rigorous test harness

## Quick start
```bash
cd /Users/chevinjeon/Desktop/autonomous-quantum-discovery-lab
python3 autonomous_quantum_lab.py
```

## Frontend (React + Tailwind)
The UI is a standalone React app under `frontend/` with Recharts visualizations.

```bash
cd /Users/chevinjeon/Desktop/autonomous-quantum-discovery-lab/frontend
npm install
npm run dev
```

Then open the local URL printed by Vite.

Optional run logging:
Set `VITE_RUN_LOG_ENDPOINT` to a webhook/API endpoint to capture "Run" clicks.
```bash
VITE_RUN_LOG_ENDPOINT="https://your-api.example.com/run" npm run dev
```

## Portfolio risk lab
Synthetic market generator + portfolio metrics (foundation for QGAN + QUBO).

```bash
python3 -m portfolio_lab.market
```

QUBO-based allocation loop:
```bash
python3 -m portfolio_lab.lab --assets 6 --target-assets 3 --steps 30
```

Export results for Excel:
```bash
python3 -m portfolio_lab.lab --assets 6 --target-assets 3 --steps 30 --export-csv portfolio_runs.csv
```

## What you’ll see
- Best theta found by brute-force and SPSA
- Recent lab notebook entries (diachronic trace)
- Test suite results

## File map
- `autonomous_quantum_lab.py` — autonomous quantum loop + optimizers + tests
- `hybrid_lab/` — hybrid physical-quantum scaffolding (sensor noise → error map → control)
- `qiskit_backend.py` — Qiskit Aer backend for real circuit simulation
- `multi_qubit_lab.py` — 2–4 qubit SPSA demo with a toy Hamiltonian

## Next upgrades (ideas)
- Add depolarizing + amplitude damping noise
- Scale to 2–4 qubits with a toy Hamiltonian
- Add convergence plots
- Swap backend to Qiskit/Aer with the same interface

## Qiskit Aer backend (real circuit simulation)
Install Qiskit:
```bash
pip install qiskit qiskit-aer
```

Example usage:
```python
from autonomous_quantum_lab import AutonomousQuantumLab, spsa_optimize
from qiskit_backend import QiskitAerBackend, QiskitBackendConfig

backend = QiskitAerBackend(QiskitBackendConfig(seed=42))
lab = AutonomousQuantumLab(backend)
best = spsa_optimize(lab, shots=500, p_flip=0.05, steps=40, a=0.6, c=0.2)
print(best.theta, best.measured_energy)
```

CLI usage:
```bash
python3 autonomous_quantum_lab.py --backend qiskit
```

## Plots (Option C)
Install matplotlib:
```bash
pip install matplotlib
```

Run with plots:
```bash
python3 autonomous_quantum_lab.py --plot
python3 autonomous_quantum_lab.py --plot --plot-file plots.png
```

## Multi-qubit demo (Option B)
Run a 2–4 qubit SPSA optimization on a toy Hamiltonian:
```bash
python3 multi_qubit_lab.py --qubits 3 --steps 50 --shots 500 --plot
```

## Hybrid physical-quantum lab (scaffold)
This adds a minimal pipeline for:
- synthetic sensor noise (stand-in for Isaac Sim)
- mapping physical disturbance → quantum error rates
- training a control policy against disturbances

Run the hybrid demo:
```bash
python3 -m hybrid_lab.train_hybrid
```

Note: `IsaacSimNoiseSource` is a placeholder. Swap in your Isaac Sim
sensor stream or log replay by implementing `next_sample()` there.

## What your run actually demonstrates
Output
```
Best theta: 3.1641
Best energy: -0.9900
Total steps: 40
```

Recall:
The true optimum for this problem is:
- theta ≈ pi ≈ 3.1416
- Energy = cos(pi) = -1

So your system converged to:
- theta ≈ 3.1641 (extremely close to pi)
- Energy ≈ -0.9900 (within ~1% of the theoretical optimum)

That is excellent, especially with noise injected. This shows the agent
autonomously discovered the optimal quantum parameter under noise.

Hybrid behavior observed in the log:
```
step=36 theta=3.2895 E=-0.9550 p_flip=0.0130
step=37 theta=3.3478 E=-0.9600 p_flip=0.0119
step=38 theta=3.2941 E=-0.9600 p_flip=0.0125
step=39 theta=3.3491 E=-0.9100 p_flip=0.0139
step=40 theta=3.2925 E=-0.9250 p_flip=0.0131
```

Key observations:
- The optimizer explores around pi.
- It adapts as noise probability (p_flip) changes.
- It does not collapse or diverge.
- The lab runs experiments, logs diachronically, and improves the objective.

What you can confidently say:
I built an autonomous quantum experiment system that automatically tunes a
noisy quantum circuit using closed-loop optimization and diachronic learning.
It converges to the optimal quantum state without human intervention.

Why this is a strong MVP:
- Autonomous experiment loop
- Noise modeling
- Hybrid optimization
- Diachronic memory
- Convergence behavior
- Deterministic reproducibility
- CLI demo
- Logs for explainability
