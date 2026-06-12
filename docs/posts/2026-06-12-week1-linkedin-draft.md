# Week 1 LinkedIn post — DRAFT (not yet published)

Plain text below is LinkedIn-ready (no markdown rendering there).
Source material: BUILD_LOG.md 2026-06-11/12 and
docs/experiments/2026-06-12-extraction-v1-first-live-run.md.

---

**A Bloomberg seat costs ~$30k a year. Claude just did one of its jobs for $280.**

Not saying anyone's losing their job — Bloomberg does a thousand things and I did one of them, badly-maybe (more on that below). But here are some findings from research I've been doing on ASX earnings announcements:

I pointed Claude at 26 earnings filings from the ASX's biggest names (CBA, BHP, Wesfarmers, NAB...) and asked for structured financials — revenue, NPAT, EPS, dividends — with a confidence score and a verbatim quote for every single number.

What I found:

💸 **14 cents a document.** The full corpus cost $4.40. Scaled to every earnings doc the entire ASX 300 files in a year: ~$280. The "this will be too expensive" objection died in an afternoon.

🔁 **It agrees with itself.** Where the same results appear in two documents (media release vs the statutory report), the extractions matched — a consistency check I didn't even design for.

🕵️ **Zero fabricated quotes — but my first eval lied to me.** I audited all 176 cited quotes against the source documents. Exact-match flagged 20% as "missing." Every single one was real; my PDF parser's line breaks just didn't match the model's spacing. If I'd shipped that eval, I'd be reporting hallucinations that were actually my own parser. Your eval can quietly measure the wrong part of your system.

🏦 **The hard part isn't extraction, it's definitions.** CBA reports two different EPS numbers and two different NPATs depending on which document you read. The model has to be told which one "wins" — and so does the human labeling the ground truth.

What I don't have yet: an accuracy number. That needs hand-labeled ground truth, which is next. No eval, no claims — that's the whole point of this project.

Building it in public: github.com/Taylor-Hobbs/asx

---

## Notes to self before posting

- The "badly-maybe" in line 2 carries the honesty disclaimer — if it gets
  edited out, restore something in that spot or the post overclaims until
  the last paragraph.
- Bloomberg anchor is the terminal price (~$30k/seat) deliberately —
  verifiable, unlike analyst-salary claims.
- Emoji bullets are LinkedIn-native; strip if they read as off-voice.
- Held back for a future post: the Max-plan / Agent SDK billing
  investigation — better told once the runner experiment (pre-registered in
  docs/experiments/) has results: "same model, same prompt, two execution
  paths."
