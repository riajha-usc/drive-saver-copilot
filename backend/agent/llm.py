"""Narration layer.

The agent's numbers are computed deterministically. The LLM only turns the solved
decision into operator-facing language, which keeps the prescription auditable
and lets the prototype run with no API key at all: without one, or on any API
error, the deterministic narrator produces the same three fields.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a maintenance engineer writing the action card an operator
reads on the plant floor.

You are given a solved decision: the risk numbers, the root cause, the chosen
parameter adjustment and its projected effect. All of it is already computed.

Rules:
- Never invent, recompute or contradict a number. Use only the figures given.
- Say what to change, by how much, and what it buys, in that order.
- Plain industrial English. No hedging, no marketing, no em dashes.
- headline: under 90 characters, the action and the hours gained.
- explanation: 2 to 3 sentences on why this motor is at risk and why this fix works.
- operator_instruction: one imperative sentence a technician can act on."""


class NarrationOut(BaseModel):
    headline: str = Field(max_length=140)
    explanation: str
    operator_instruction: str


def _facts_block(ctx: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in ctx.items())


def deterministic_narration(ctx: dict) -> NarrationOut:
    """Template narrator. Always available, no network."""
    if ctx["action_type"] == "stop_now":
        return NarrationOut(
            headline=(f"Take {ctx['asset_id']} off line, no single safe change "
                      f"clears {ctx['unresolved']}"),
            explanation=(
                f"{ctx['asset_id']} is at {ctx['risk_band']} risk of {ctx['mode_name']} "
                f"({ctx['failure_probability_pct']} within the reference horizon) and "
                f"{ctx['physical_margin']}. Every torque and speed trim inside the drive's "
                f"operating range leaves the fault in place, so there is no adjustment that "
                f"carries this asset to the {ctx['hours_to_window']} hour window."),
            operator_instruction=("Take the asset off line and raise a work order against "
                                  f"{ctx['mode_name']}."),
        )

    if ctx["action_type"] == "no_action":
        return NarrationOut(
            headline=f"No action needed, risk is {ctx['risk_band']} at {ctx['failure_probability_pct']}",
            explanation=(f"{ctx['asset_id']} is running inside every physical limit. "
                         f"The closest limit is {ctx['physical_margin']}. "
                         f"Projected remaining life is {ctx['baseline_rul_hours']} hours."),
            operator_instruction="Continue at the current setpoints and recheck at the next telemetry poll.",
        )

    gain = ctx["rul_extension_hours"]
    # The summary is a sentence opener elsewhere, so lower case it mid sentence.
    action = ctx["adjustment_summary"][0].lower() + ctx["adjustment_summary"][1:]
    if ctx["action_type"] == "schedule_maintenance":
        instruction = (f"{ctx['adjustment_summary']} and keep the drive under watch until then.")
    elif ctx["action_type"] == "stop_now":
        instruction = ("Take the asset off line now, no setpoint change reaches the "
                       f"{ctx['hours_to_window']} hour window.")
    else:
        instruction = (f"{ctx['adjustment_summary']} on the drive and hold that setpoint "
                       f"through the {ctx['hours_to_window']} hour maintenance window.")
    return NarrationOut(
        headline=f"{ctx['adjustment_summary']} to add about {gain} hours before {ctx['mode_name']}",
        explanation=(
            f"{ctx['asset_id']} is at {ctx['risk_band']} risk of {ctx['mode_name']} "
            f"({ctx['failure_probability_pct']} within the reference horizon), with roughly "
            f"{ctx['baseline_rul_hours']} hours of useful life left. The dominant driver is "
            f"{ctx['primary_driver']} at {ctx['primary_driver_share_pct']} of the risk, and {ctx['physical_margin']}. "
            f"Choosing to {action} moves the operating point back inside the limit and lifts projected life to "
            f"{ctx['projected_rul_hours']} hours, at {ctx['throughput_loss_pct']} percent output loss."),
        operator_instruction=instruction,
    )


def llm_narration(ctx: dict) -> tuple[NarrationOut, str]:
    """Try the LLM, fall back to the template on any failure."""
    if not config.ANTHROPIC_API_KEY:
        return deterministic_narration(ctx), "deterministic"
    try:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model=config.LLM_MODEL, temperature=0, max_tokens=700)
        structured = llm.with_structured_output(NarrationOut)
        result = structured.invoke(
            [("system", SYSTEM_PROMPT), ("human", _facts_block(ctx))])
        return NarrationOut.model_validate(result), "llm"
    except Exception as exc:  # narration must never block a prescription
        log.warning("LLM narration failed, using deterministic narrator: %s", exc)
        return deterministic_narration(ctx), "deterministic"
