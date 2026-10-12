import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE / "orbitlab_interpreter_train_v9_master.jsonl"
output = HERE / "orbitlab_v9_tinker.jsonl"

converted = []
errors = []

with source.open("r", encoding="utf-8-sig") as f:
    for line_no, line in enumerate(f, 1):
        try:
            item = json.loads(line)
            system = item["systemInstruction"]
            contents = item["contents"]

            system_text = "\n".join(
                part["text"]
                for part in system.get("parts", [])
                if "text" in part
            )

            messages = [{"role": "system", "content": system_text}]
            for message in contents:
                role = message.get("role")
                text = "\n".join(
                    part["text"]
                    for part in message.get("parts", [])
                    if "text" in part
                )

                if role == "user":
                    messages.append({"role": "user", "content": text})
                elif role == "model":
                    messages.append({"role": "assistant", "content": text})

            if (
                len(messages) < 3
                or messages[-1]["role"] != "assistant"
                or not messages[-1]["content"].strip()
                or not any(m["role"] == "user" for m in messages)
            ):
                raise ValueError("Missing user prompt or assistant target")

            converted.append({"messages": messages})

        except Exception as e:
            errors.append(f"Line {line_no}: {e}")

if errors:
    print(f"FAILED: {len(errors)} invalid records.")
    print("\n".join(errors[:20]))
    raise SystemExit(1)

if len(converted) != 3800:
    print(f"STOP: expected 3800 records, found {len(converted)}")
    raise SystemExit(1)

with output.open("w", encoding="utf-8", newline="\n") as f:
    for item in converted:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"PASS: converted {len(converted)} records")
print(f"Output: {output.resolve()}")
print("Original dataset unchanged; no training was started.")
