# Representative Synthetic Project

This directory is a fictional, internally coherent tutoring project used by the
test suite. It contains no real student records. Real examples informed the kinds
of records and conversational rhythms represented here, but names, contact
details, dates, scores, resource names, lesson language, and identifiers were
created for this repository.

## Layout

`manifest.json` is the entry point. It declares the three student directories,
the expected match outcome for each lesson scenario, and sentinel values used to
test the privacy boundary.

Each student directory contains:

- `dashboard/`: source-shaped profile, test, intake-note, and lesson records;
- `granola/`: meeting metadata and raw-but-curated transcript text;
- `generated/`: an imperfect LLM draft and reviewed final summary for each
  completed matched lesson; and
- `expected/`: normalized application records, the AI-safe profile projection,
  and exact Dashboard-reported score expectations.

Structured source records use JSON. Long transcripts use UTF-8 plain text with
Granola-style `Microphone:` and `System audio:` labels. Each meeting record stores
the SHA-256 digest of its transcript so accidental text drift is visible.

## Privacy Boundary

Dashboard profiles deliberately include reserved fictional contact values. They
exercise the same restricted-data boundary that production records require. The
AI-safe profile is an allowlisted projection: contact information and unknown
upstream fields never flow into normalized academic records, transcripts,
summary-generation inputs, embeddings, or retrieval documents.

The sentinel strings in `manifest.json` make that rule mechanically testable.

## Authority and Expected Results

Dashboard records are the sole authority for recorded scores, reported
superscores, reviewed lesson summaries, and homework. Expected score files copy
those values exactly; fixture code does not recalculate them.

The manifest's match decisions are fixture-only test oracles. They describe the
correct result against which future matching logic can be evaluated. They are
not inputs that production matching code may use. In particular, the ambiguous
Maya scenario contains two plausible Dashboard candidates and requires the
matcher to refuse an automatic selection.

## Validation

`load_synthetic_project()` reads this layout through the manifest.
`validate_synthetic_project()` checks identifiers, references, chronology,
supersession, transcript hashes and lengths, scenario outcomes, score authority,
draft/final order, final-summary authority, and privacy sentinels across the
entire project.
