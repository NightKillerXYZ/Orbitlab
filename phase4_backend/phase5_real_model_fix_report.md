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
