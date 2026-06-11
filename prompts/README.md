# Prompts

Versioned prompt artifacts. Rules:

- One file per announcement type per version: `earnings_v1.md`, `guidance_v1.md`, …
- **Existing versions are immutable.** A change — however small — is a new version file.
  Eval results are keyed to prompt versions; editing in place would corrupt history.
- No prompt ships without an eval run showing it matches or beats the incumbent
  on the golden set (see `docs/eval-methodology.md`).
