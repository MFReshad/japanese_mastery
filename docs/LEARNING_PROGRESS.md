# Learning progress architecture

## Individual items

Vocabulary, direct kanji, and canonical kanji examples keep independent `item_progress` rows. Individual status remains based on attempts, lifetime accuracy, current correct streak, and latest result. Practicing an example does not increment direct kanji or vocabulary attempts.

## Main kanji strength

For a kanji source with examples, the main status is derived from distinct example statuses:

- **New:** no examples have been practiced.
- **Learning:** at least one has been practiced and neither Weak nor Mastered applies.
- **Weak:** more than 50% of practiced examples are Weak, including when the only practiced example is Weak.
- **Mastered:** all examples have been practiced and at least 90% are Mastered.

Unpracticed examples are excluded from the weakness denominator. A kanji with no examples falls back to its independent direct-practice status.

`app.services.kanji_strength` is the authoritative Python and SQL implementation. Library, Study detail, Progress coverage, Management kanji responses, and direct-kanji Practice status filters consume that rule. Direct status and attempts remain separately available and must be labelled **Direct Practice** in UI.

## Example identity and history

Each printed `KanjiExample` remains a source occurrence with its own meaning, importance, manual knowledge mark, order, book, chapter, and parent kanji source. Automatic progress is keyed by `CanonicalKanjiExample.id`. Canonical identity is the Unicode-NFKC-normalized word plus normalized reading; different readings never merge automatically.

Management updates send existing occurrence IDs so corrections and reordering update rows in place. Changing a word or reading relinks that occurrence to the appropriate canonical identity without rewriting history. New examples omit occurrence IDs. Removing an example that has progress or source history remains guarded.

Management creation and imports resolve canonical identity automatically. PostgreSQL uses the normalized-key uniqueness constraint with an atomic insert-or-reuse operation, so concurrent requests cannot create duplicate canonical identities. Reimports retain matching source-occurrence IDs, source-local marks, and ordering relationships rather than replacing every example row.

Practice questions and answers use the canonical ID as `item_id` and retain the original `source_entry_id`, prompt, answers, and reveal context. A session containing the same canonical example through several selected books asks it only once. Study, Review, Progress, Practice filters, and parent-kanji strength join source occurrences to shared progress through `canonical_id`.

Migration `0016_canonical_examples` creates and assigns canonical identities. It preserves a single existing progress row as-is. When several duplicate occurrences contain progress, it reconstructs the shared counters only when answer history exactly accounts for all recorded attempts. Otherwise it aborts transactionally and requires explicit review; it never guesses or blindly sums counters. Historical question and answer rows keep their primary keys and source references.

## Multi-kanji words

Equivalent word-and-reading pairs share automatic progress across every `KanjiSource`, including across books. They are not linked to canonical `Vocabulary`, so vocabulary progress remains independent. A word containing several characters is not propagated to those characters: only identical example word-and-reading identities share progress.

Within one parent `KanjiSource`, canonical examples are counted distinctly for main-kanji strength even if malformed source data repeats the same occurrence.
