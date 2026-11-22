# Learning progress architecture

## Individual items

Vocabulary, direct kanji, and kanji examples keep independent `item_progress` rows. Individual status remains based on attempts, lifetime accuracy, current correct streak, and latest result. Practicing an example does not increment direct kanji or vocabulary attempts.

## Main kanji strength

For a kanji source with examples, the main status is derived from distinct example statuses:

- **New:** no examples have been practiced.
- **Learning:** at least one has been practiced and neither Weak nor Mastered applies.
- **Weak:** more than 50% of practiced examples are Weak, including when the only practiced example is Weak.
- **Mastered:** all examples have been practiced and at least 90% are Mastered.

Unpracticed examples are excluded from the weakness denominator. A kanji with no examples falls back to its independent direct-practice status.

`app.services.kanji_strength` is the authoritative Python and SQL implementation. Library, Study detail, Progress coverage, Management kanji responses, and direct-kanji Practice status filters consume that rule. Direct status and attempts remain separately available and must be labelled **Direct Practice** in UI.

## Example identity and history

Kanji-example progress is keyed by `KanjiExample.id`. Management updates send existing IDs so corrections and reordering update rows in place. New examples omit IDs. Removing an example that has progress, a generated practice question, or answer history is rejected; history is never silently reassigned to another word.

No database migration is required for this policy.

## Multi-kanji words

An example belongs to one `KanjiSource`. Equivalent words may independently appear under other sources, and `KanjiExample` is not linked to canonical `Vocabulary`. The system therefore does not propagate an attempt to other kanji or vocabulary. Supporting cross-kanji aggregation would require an explicit canonical example/membership model and is intentionally outside the current implementation.
