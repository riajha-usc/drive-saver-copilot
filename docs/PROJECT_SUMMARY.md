# Drive-Saver Copilot: Project Summary

**Agentic prescriptive maintenance for variable frequency drives and electric motors.**

Theme 1: Agentic Predictive Maintenance Studio

- Live demo: https://drive-saver-copilot-138499493256.us-central1.run.app
- Source code: https://github.com/riajha-usc/drive-saver-copilot

## The problem

Predictive maintenance tools stop at a warning: "this motor will fail in 20
hours." The operator is left to work out what to do, under time pressure, and the
answer is often an unplanned stop in the middle of a production run. For a
plant, that stop is the expensive part: lost output, idle crews and emergency
repair.

## Our solution

Drive-Saver Copilot turns the warning into an instruction. For a motor at risk,
it finds the smallest change to the drive's torque and speed setpoints, or a
maintenance action, that pushes the failure past the next planned maintenance
window. The motor keeps running until the stop that was already scheduled.

It works in three steps:

1. **Predict.** Five failure models score overall risk and each failure mode.
   Each model is chosen automatically from XGBoost, LightGBM and a baseline on
   validation data, with every candidate tracked in MLflow.
2. **Explain.** SHAP identifies which signals drive the risk and which control
   lever moves them.
3. **Prescribe.** A LangGraph agent simulates 167 torque, speed and maintenance
   options, rejects any that would trigger a different failure, and picks the
   smallest one that reaches the operator's maintenance window. If no safe change
   exists, it says stop rather than promising hours it cannot deliver.

Every recommendation shows its reasoning step by step, and every upload gets a
data quality report before its predictions are trusted.

## Impact

On the AI4I 2020 dataset's 314 critical motors, the agent finds a safe, working
prescription for 303 of them (96 percent) in about 30 milliseconds each. None of
its prescriptions trades one failure for another. Using illustrative plant costs
(8 hours of unplanned downtime at $1,800 per hour plus a $2,500 emergency
callout), the median net benefit is about $16,400 per motor saved from an
unplanned stop.

## What makes it different

- **Prescriptive, not just predictive.** It answers "what should I change",
  not only "what will break."
- **Physics grounded.** Safety guards encode the drive's physical limits, so a
  fix is never a trade for a different failure.
- **Honest by design.** Estimates are labelled as estimates, and the prototype
  never claims to have changed a real drive.

Built with Python, XGBoost, LightGBM, SHAP, MLflow, LangGraph, FastAPI, React and
Docker, and deployed on Google Cloud Run.
