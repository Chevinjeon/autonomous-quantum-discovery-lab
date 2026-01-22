# autonomous-quantum-discovery-lab

Autonomous quantum discovery lab MVP. This repo demonstrates a closed-loop
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
python quantum_mvp.py
```

## What you’ll see
- Best theta found by brute-force and SPSA
- Recent lab notebook entries (diachronic trace)
- Test suite results

## File map
- `quantum_mvp.py` — autonomous quantum loop + optimizers + tests
- `hybrid_lab/` — hybrid physical-quantum scaffolding (sensor noise → error map → control)

## Next upgrades (ideas)
- Add depolarizing + amplitude damping noise
- Scale to 2–4 qubits with a toy Hamiltonian
- Add convergence plots
- Swap backend to Qiskit/Aer with the same interface

## Hybrid physical-quantum lab (scaffold)
This adds a minimal pipeline for:
- synthetic sensor noise (stand-in for Isaac Sim)
- mapping physical disturbance → quantum error rates
- training a control policy against disturbances

Run the hybrid demo:
```bash
python -m hybrid_lab.train_hybrid
```

Note: `IsaacSimNoiseSource` is a placeholder. Swap in your Isaac Sim
sensor stream or log replay by implementing `next_sample()` there.
