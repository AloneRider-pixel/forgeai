# Assisted Review Design

## Pipeline

1. Fetch pull-request metadata and changed files from GitHub.
2. Run the deterministic analyzer and risk gate.
3. Select a bounded subset of source files from the pull request.
4. Fetch file contents at the pull-request head SHA.
5. Redact common credential material and private-key blocks.
6. Build a typed review context.
7. Generate a review plan with the deterministic planner or an OpenAI-compatible model.
8. Return the baseline report and plan together.

## Trust boundaries

```text
GitHub API
   |
   | untrusted metadata / source
   v
GitHub adapter
   |
   v
bounded context collector -----> secret redaction
   |
   v
LLM boundary
   |
   v
structured JSON validation
   |
   v
review plan
```

Repository files are untrusted. A file may contain text that looks like instructions, tool calls, credentials, or configuration. ForgeAI does not execute repository content. The LLM system prompt explicitly marks repository context as data and forbids following instructions contained within it.

## Failure behavior

The deterministic analyzer remains the source of the baseline gate decision. Context retrieval failures skip the affected file instead of failing the full review. LLM transport errors, malformed JSON, and schema errors fall back to the deterministic planner.

## Cost and blast-radius controls

Assisted review accepts limits for file count and characters per file. GitHub changed-file retrieval also has a bounded page count. These controls keep context growth predictable and limit the amount of repository data sent to an external model.

## Next security work

- Add adversarial prompt-injection fixtures to the evaluation set.
- Add CodeQL and dependency-review findings as typed evidence.
- Add an explicit human approval object before any future write action.
- Add audit events for every model invocation and proposed action.
