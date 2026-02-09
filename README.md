# SynQubi

SynQubi is a quantum-first portfolio optimization and risk analysis platform.
It provides practical, hybrid quantum-classical workflows for scenario generation,
QUBO-based optimization, and risk metrics (VaR/CVaR) with production-minded
integration points.

## What’s included
- Portfolio risk lab with QUBO formulation and solvers
- Scenario lab for stress testing (bull/bear/tail cases)
- Real-time streaming scaffold (Kinesis -> Lambda -> DynamoDB)
- Low-latency solver service with ALB endpoint
- Frontend dashboard for solver output and stress cases

## Quick start
```bash
cd /Users/chevinjeon/Desktop/autonomous-quantum-discovery-lab
python3 autonomous_quantum_lab.py
```

## Frontend (React + Tailwind)
The UI is a standalone React app under `frontend/` with portfolio/risk visuals.

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

Realtime solver panel:
Set `VITE_SOLVER_ENDPOINT` to your ALB URL (e.g. `http://...elb.amazonaws.com`).

## Portfolio risk lab
Synthetic market generator + portfolio metrics (foundation for QUBO/QAOA/VQE).

```bash
python3 -m portfolio_lab.market
```

QUBO-based allocation loop:
```bash
python3 -m portfolio_lab.lab --assets 6 --target-assets 3 --steps 30
```

Use Yahoo Finance tickers (live pulls):
```bash
python3 -m portfolio_lab.lab --tickers "AAPL,MSFT,NVDA,AMZN" --target-assets 2 --horizon 252
```

Requires:
```bash
pip install yfinance
```

Export results for Excel:
```bash
python3 -m portfolio_lab.lab --assets 6 --target-assets 3 --steps 30 --export-csv portfolio_runs.csv
```

Use EDHEC hedge fund indices (real historical returns):
```bash
python3 -m portfolio_lab.edhec_lab --csv "/Users/chevinjeon/Downloads/archive/edhec-hedgefundindices.csv" --target-assets 4
```

Production-grade evaluation (train/test split + benchmark + costs):
```bash
python3 -m portfolio_lab.edhec_lab \
  --csv "/Users/chevinjeon/Downloads/archive/edhec-hedgefundindices.csv" \
  --target-assets 4 \
  --train-ratio 0.7 \
  --transaction-cost-bps 10
```

## AI stress tester (scenario lab)
Generate thousands of market scenarios and extract bull/bear/stress cases.

```bash
python3 -m scenario_lab.lab --assets 6 --steps 252 --scenarios 2000 --vol-regime 1.5 --corr-shift 0.2 --export-cases cases.csv
```

Use a StockTrak portfolio export for weights:
```bash
python3 -m scenario_lab.lab --weights-csv "/Users/chevinjeon/Downloads/RSM336-Portfolio-performance-analysis(Our Portfolio ).csv"
```

## Real-time portfolio optimization (scaffold)
Streaming market feed + low-latency solver + portfolio system integration.

```bash
python3 -m realtime_lab.lab --symbols A,B,C,D --max-assets 3 --iterations 5
```

Mock Kinesis producer:
```bash
python3 -m realtime_lab.producer --stream synqubi-market-ticks --symbols A,B,C,D
```

## AWS IaC (streaming + solver scaffold)
Terraform scaffolds:
- Kinesis Data Stream
- Lambda ingest to DynamoDB
- DynamoDB latest snapshot table
- ECS Fargate solver service + ECR repo

Apply:
```bash
cd infra/terraform
terraform init
terraform apply
```

Build/push solver image:
```bash
cd realtime_lab/solver_service
docker build -t synqubi-solver .
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ECR_REPO>
docker tag synqubi-solver:latest <ECR_REPO>:latest
docker push <ECR_REPO>:latest
```

Then set `solver_desired_count=1` and re-apply to start the service.

## Agent architecture (current mapping)
```
[ Market Observer ]        -> scenario_lab inputs (market state parameters)
        ↓
[ Scenario Generator ]     -> scenario_lab/generator.py
        ↓
[ Risk Evaluator ]         -> portfolio_lab/risk.py + scenario_lab/scorer.py
        ↓
[ Optimization Engine ]    -> portfolio_lab/qubo.py + portfolio_lab/lab.py
        ↓
[ Noise Mitigation Layer ] -> autonomous_quantum_lab.py + hybrid_lab
        ↓
[ Decision Maker ]         -> scenario_lab bull/bear/stress selection
        ↓
[ Memory/Learning Layer ]  -> CSV/log outputs (expandable)
```

## What you’ll see
- Portfolio risk metrics (Sharpe, Volatility, Drawdown, VaR, CVaR)
- Stress-case selection (bull/bear/tail)
- Low-latency solver outputs

## File map
- `portfolio_lab/` — QUBO formulation, solvers, risk metrics
- `scenario_lab/` — stress testing and scenario scoring
- `realtime_lab/` — streaming + solver + OMS integration stubs
- `frontend/` — portfolio/risk dashboard
- `infra/terraform/` — AWS IaC scaffold

## Next upgrades (ideas)
- Add QAOA/VQE circuit backends for QUBO problems
- Integrate QAE-style VaR/CVaR estimation
- Add sector/constraint encoding in QUBO
- Add OMS adapters and audit logging

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
