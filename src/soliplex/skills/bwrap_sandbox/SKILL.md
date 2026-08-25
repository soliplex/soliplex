---
name: bwrap_sandbox
description: |
    This skill runs Python in a bubblewrap
    sandbox. Each turn gets a scratch working directory that lasts for the
    duration of that turn, plus read-only access to uploaded files mounted
    under '/sandbox/volumes'.
metadata:
  sandbox_volumes_path: "/sandbox/volumes"
  sandbox_workdir_path: "/sandbox/work"
---

# Sandbox

This skill runs Python in a bubblewrap sandbox.
Use it to compute results from files.

## When to use the sandbox

Use the sandbox if **any** of these is true:

- The task references one or more files uploaded
  under `/sandbox/volumes/thread` or `/sandbox/volumes/room`.
- The task asks for a number, count, table, or other value derived from data.
- You were about to state a computed result without actually computing it.

Do NOT use the sandbox if **any** of these is true:

- The question is about definitions, explanations, or concepts.
- The answer is already stated in the conversation.
- The task is to write code for the user to run, not to execute code yourself.
- The task is vague ("analyze the files", "take a look")
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
- `list_volume_files(volume)` — returns the sandbox paths of the files in
  the given volume. `volume` is `"thread"` or `"room"`.
- `run(command, environment_name=None, timeout=None)` — run a shell command
  in the sandbox. `command` is either a single string (run via `sh -c`) or a
  list of strings (executable first, then one element per argument).
- `run_python(script, environment_name=None, timeout=None)` — run a Python
  script. `script` is the full source as one string.

When calling `run` and `run_python`, `environment_name` and `timeout` are both
optional and fall back to the values this skill was configured with.
Always pass `environment_name` explicitly, using a name that
`list_environments` returned — the configured default is not visible to you
and may not be the environment you want.

## Workflow

1. **Pick an environment.** Run `list_environments`, which returns a list
   of dictionaries shaped like:

   ```python
   {
      "name": "pandas",
      "description": "Minimal Python with Pandas",
      "dependencies": ["pandas"],
   }
   ```

   Apply these rules in order:
   - If the list is empty, stop and tell the user the skill
     is not configured — do not proceed.
   - If the list contains exactly one environment, use its `name`.
   - Otherwise, pick the `name` of the first environment whose `dependencies`
     include a library the task needs (e.g. `pandas` for tabular data,
     `numpy` for numeric work, `pillow` for images).  If no environments
     match, use the `name` of the first entry in the list.

2. **List files in both volumes.**  This step is mandatory — do not skip it,
   even if the task seems to involve one volume.  Run both:

   ```python
   list_volume_files("thread")
   list_volume_files("room")
   ```

   Each call returns a list of absolute paths as seen from inside the
   sandbox, or an empty list if the volume has no files:

   ```python
   ["/sandbox/volumes/thread/orders.csv",
    "/sandbox/volumes/thread/notes.txt"]
   ```

   Pass these paths straight to `run` or `run_python` — they are already
   the paths your script should open.

   If both calls return no files, proceed without inputs.

3. **Read only the files you need.** Do not dump every file — pick the
   ones the task actually requires. If `room` has any files, read them too:
   they often contain rules or reference data the task depends on.

   To peek at a file's shape before writing analysis code, use the `run`
   tool with a list `command`, e.g.

   ```python
   run(command=["head", "-n", "5", "/sandbox/volumes/thread/orders.csv"],
       environment_name="<selected-environment>")
   ```

   (or `["wc", "-l", <path>]`, `["file", <path>]`, etc.).  For anything
   beyond a quick peek — parsing, filtering, joining — read the file inside
   the script you pass to `run_python` in step 4 rather than running `cat`
   on the whole file.

4. **Run a Python script in the sandbox.** Pass the source as the `script`
   argument to `run_python`:

   ```python
   run_python(script="<python source>", environment_name="<selected-environment>")
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

1. `list_environments()` — shows one environment named `pandas`
   with `pandas` in its dependencies. Use it.

2. `list_volume_files("thread")` — returns
   `["/sandbox/volumes/thread/orders.csv"]`.
   `list_volume_files("room")` — returns `[]`.
   Continue with just the thread input.

3. Run:

   ```python
   run_python(
       script="""import pandas as pd
   df = pd.read_csv('/sandbox/volumes/thread/orders.csv')
   print(f"Total: {df['amount'].sum():.2f}")
   """,
       environment_name="pandas",
   )
   ```

   — prints `Total: 48215.00`.

4. Report to the user: "Total order value: $48,215.00."
