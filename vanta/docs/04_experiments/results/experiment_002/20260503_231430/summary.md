# Experiment 002 Local Run

Status: completed
Fixture count: 7
Baseline: openclaw_agent_local/openai-codex/gpt-5.4-mini_verifier_final_answer_and_raw_trace
Treatment: openclaw_agent_local/openai-codex/gpt-5.4-mini_verifier_structured_evidence_packet

## Final Answer

- verifier_false_accept_rate: 0.6666666666666666
- verifier_false_reject_rate: 0.25
- evidence_sufficiency_score: 0.0
- verifier_brier_score: 0.39357142857142857
- request_evidence_rate: 0.0
- abstain_rate: 0.2857142857142857


## Raw Trace

- verifier_false_accept_rate: 1.0
- verifier_false_reject_rate: 0.0
- evidence_sufficiency_score: 0.0
- verifier_brier_score: 0.4145571428571428
- request_evidence_rate: 0.0
- abstain_rate: 0.0


## Structured Evidence Packet

- verifier_false_accept_rate: 0.0
- verifier_false_reject_rate: 1.0
- evidence_sufficiency_score: 1.0
- verifier_brier_score: 0.42857142857142855
- request_evidence_rate: 0.0
- abstain_rate: 1.0


Interpretation: this is an OpenClaw local harness verifier run and must not
be described as a pure model-only result or broad validation of H2.
