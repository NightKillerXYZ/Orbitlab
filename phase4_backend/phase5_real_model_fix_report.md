# Phase 5 real-model fix (`phase5-real-model`)

## Step 1 — system message (read, then fixed)

EXACT text the client sent before this fix (`INTERPRETER_SYSTEM_PROMPT`):

"You are an OrbitLab Experiment Interpreter. Convert the user's natural-language orbital-simulation request into the exact OrbitLab Experiment JSON structure. Output ONLY the JSON object, with no surrounding text, explanation or markdown fences."

Character-by-character comparison with the training text: DIFFERENT (different
wording throughout; e.g. "You are an ..." vs "The model is an ...", and none
of the Rules bullets were present). Replaced the constant with the training
text verbatim (single `INTERPRETER_SYSTEM_PROMPT`, one place). New test
`test_system_prompt_is_training_text` asserts the request's first message
equals that constant exactly.

## Step 2 - max_tokens + truncation

- Setting `ORBITLAB_MODEL_MAX_TOKENS` (default 1500; both settings branches + `.env.example` placeholder), sent as `"max_tokens"` in the chat body (covered by `test_body_contains_max_tokens`).
- `finish_reason: "length"` raises `InterpreterOutputTruncatedError` ("Model output was cut off ... raise ORBITLAB_MODEL_MAX_TOKENS and retry") - a plain `InterpreterClientError`, deliberately NOT an `InterpreterUnavailableError`, so it is never retried (covered by `test_truncated_output_no_retry`, single attempt).

## Step 3 - `--skip-extract`

`scripts/smoke_real_model.py --skip-extract` skips the extractor and uses 6 prepared front-step-form sentences with prebuilt sent data (sma already converted, names filled); interpreter, verify and validator run as before. Unit test uses a fake client and a patched-out extractor (PASS verdict, extractor never called).

## Step 4 - counts

- Backend (`phase4_backend`, `python -m pytest ../tests -q`): **71 passed**.
- Core (repo root, `python -m pytest orbitlab_core/tests -q`): **48 passed + 29 subtests**.
- Simulation-engine (repo root, `python -m pytest simulation_engine/tests -q`): **23 passed**.
- Total **142 + 29 subtests, 0 failed**.
- RUNBOOK gained "Extractor setup" (`EXTRACTOR_*` names, OpenAI-compatible endpoint note, regex-fallback limits). `.env` confirmed gitignored; `.env.example` names-only.

## Could not verify

No live model call: no hosted key in this environment, and the script exits 2 without one (verified: names only, no values). A dummy-endpoint dry run showed the harness fails gracefully per prompt with a summary and secret-free JSON - and that the regex fallback cannot parse most free-form prompts (extract FAILs before any network), which is why `--skip-extract` exists.
