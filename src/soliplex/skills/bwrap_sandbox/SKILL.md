---
name: bwrap-sandbox
description: |
    This skill runs Python in a bubblewrap
    sandbox. Each run has a persistent working directory and read-only
    access to uploaded files mounted under '/sandbox/volumes'.
---

# Sandbox

This skill runs Python in a bubblewrap sandbox.
Use it to compute results from files.

## When to use the sandbox

Use the sandbox if **any** of these is true:

- The task references one or mor files uploaded
  under `sandbox/volumes/thread` or `sandbox/volumes/room`.
- The task asks for a number, count, table, or other value derived from data.
- You were about to state a computed result without actually computing it.

Do NOT use the sandbox if **any** of these is true:

- The question is about definitions, explanations, or concepts.
- The answer is a already stated in the conversation.
- The task is to write code for the user to run, not to execute code yourself.
- The task is value ("analyze the files", "take a look")
  with no concrete question. Ask the user what they want to know
  before running anything.

## Sandbox file layout

- `/sandbox/work/` — read/write scratch space inside the sandbox.
  Intermediate artifacts written by a script go here.
- `/sandbox/volumes/thread/` —  read-only;
  files the user uploaded to this thread. Usually the inputs for the task.
- `/sandbox/volumes/room/` — read-only;
  files shared across the room. Often contain rules, formulas,
  or reference data required for a correct answer.

## Tools

- `list_environments()` — returns available Python environments,
  each with a `name`, `description`, and set of installed `dependencies`.
- `list_volume_files(volume_name)` — returns a list of absolue paths of files
  within the given volume (`"thread"` or `"room"`).
- `run(environment, *command_args)` — run a an arbitrary shell command
   in the sandbox.
- `run_python(environment, script_text)` — run a Python script string.

## Workflow

1. **Pick an environment.** Run `list_environments`, which returns a list
   of dictionaries shaped like:

   ```python
   {
      "name": "bare",
      "description": "Minimal Python",
      "dependencies": ["pandas"],
   }
   ```

   Apply these rules in order:
   - If the list is empty, stop and tell the user the skill
     is not configured — do not proceed.
   - If the list contains exactly one environment, use its `name`.
   - Otherwise, pick the `name` of the first environment whose `dependencies`
     include a library the task needs (e.g, `pandas` for tabular data,
     `numpy` for numeric work, `pillow` for images).  If no environments match,
     use 'name' of the first entry in the list.

2. **List files in both volumes.**  This step is mandatory — do not skip it,
   even if the task seems to involve one volume.  Run both:

   ```python
   list_volume_files("thread")
   list_volume_files("room")
   ```

   Each tool prints one absolute path line, or nothing if the volume is empty:

   ```python
   /sandbox/volumes/thread/orders.csv
   /sandbox/volumes/thread/notes.txt
   ```

   If both commands print no files, proceed without inputs.

3. **Read only the files you need.** Do not dump every file — pick the
   ones the task actually requires. If `room` has any files, read them too:
   they often contain rules or reference data the task depends on.

   To peek at a file's shape before writing analysis code, use the `run` tool,
   e.g. `run(environment, "head", "-n", "5", <path>)` (or `"wc", "-l"`,
   `"file"`, etc.).  For anything beyond a quick peek — parsing, filtering,
   joining — read it inside a the script call in step 4 rather than running
   `"cat"` on the whole file.

4. **Run a Python script in the sandbox.** Pass the source as the `script_text`
   argument to `run_python`:

   ```python
   run_python(environment, script_text="<python source>")
   ```

   Write the whole program as a single string, and use real newlines between
   separate statements. `;` only works for simple statements — compound
   statements like `def`, `class`, `with`, `for`, `if`, `try` must
   start on their own line.

   Start from this skeleton and replace the `TODO`:

   ```python
   from pathlib import Path

   # Inputs (read-only): /sandbox/volumes/thread/, /sandbox/volumes/room/
   # Scratch (read-write): /sandbox/work/

   # TODO: read inputs, apply any rules from room files, compute `result`.

   print(result)
   ```

5. **On failure.**
   - Change exactly one thing per retry.
   - After 3 failed runs, stop. Report the error to the user (paste the
     `Exited with code: <N>` line and any traceback), instead of retrying
     further.

## Output

- Print the answer to stdout; only stdout is shown to the user.
- If the answer is more than ~20 rows or lines, print a short summary
  (head, counts, totals), and write the full detail to a file under
  `/sandbox/work/`.
- Do not print narration lines like "Loading data…" or "Processing…".
  Just run the script.
- After the script succeeds, report the result to the user
  in one or two sentences.

## Example

Task: user uploads `orders.csv` and asks "what's the total order value?".
A full run looks like:

1. `list_environments()` — shows one environment named `default`
   with `pandas` in its dependencies. Use it.

2. `list_volume_files("thread")` — lists `/sandbox/volumes/thread/orders.csv`.
   `list_volume_files("room")` — prints no files.
   Continue with just the thread input.

3. Run:

   ```python
   run_python("default", script_text="import pandas as pd; df = pd.read_csv('/sandbox/volumes/thread/orders.csv'); print(f\"Total: {df['amount'].sum():.2f}\")"
   ```

   — prints `Total: 48215.00`.

4. Report to the user: "Total order value: $48,215.00."
