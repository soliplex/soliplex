---
name: bwrap_sandbox
description: |
    Run shell commands and Python in a sandbox, to compute results from
    files rather than estimating them, with read-only access to uploaded
    files and a working directory to write to.
metadata:
  sandbox_volumes_path: "/sandbox/volumes"
  sandbox_workdir_path: "/sandbox/work"
---

# Sandbox

Run code to compute results from files. What is mounted, how much is in
each mount, and which packages are installed are described separately, per
request.

## When to use the sandbox

Use it if **any** of these is true:

- The task references uploaded files.
- The task asks for a number, count, table, or other value derived from
  data.
- You were about to state a computed result without actually computing it.

Do NOT use it if **any** of these is true:

- The question is about definitions, explanations, or concepts.
- The answer is already stated in the conversation.
- The task is to write code for the user to run, not to execute code
  yourself.
- The task is vague ("analyze the files", "take a look") with no concrete
  question. Ask the user what they want to know before running anything.

## Tools

- `run(command)` — run a shell command. `command` is either a single
  string (run via `sh -c`) or a list of strings (executable first, then
  one element per argument).
- `run_python(script)` — run a Python script. `script` is the full source
  as one string.
- `read_image(path)` — look at an image in the sandbox. Only in rooms
  whose model accepts images, so it may not be there. `run` and
  `run_python` return text, so this is the only way to see a picture.

Use `run` to look around — `ls` a volume, `head` a file, `wc -l` it — and
`run_python` for anything that parses, filters, or aggregates.

## Writing a script

Pass the whole program as one string, with real newlines between
statements. `;` only works for simple statements: `def`, `class`, `with`,
`for`, `if` and `try` each start on their own line.

Read inputs straight from their volume paths. Where to write depends on
whether the workspace is kept — the per-request description says which.

## Reporting a result

- Print the answer to stdout. Both stdout and stderr come back to you,
  labelled; the user sees neither, so report the result yourself in one or
  two sentences.
- If the answer runs to more than ~20 rows or lines, print a short
  summary. Where the rest goes depends on the workspace: when the
  per-request description says files there are downloadable, write it to
  one and tell the user the filename; otherwise keep the summary short
  enough to stand on its own.
- Do not print narration like "Loading data…".

## On failure

- Read the whole error. The cause is often in the middle of a traceback,
  not the last line.
- Change exactly one thing per retry.
- After 3 failed runs, stop and report the error to the user rather than
  trying again.
- A failure naming the sandbox environment is a server configuration
  problem: report it, do not retry.
