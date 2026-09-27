# Stabilization deployment and data policy

Baseline: 32 backend SQLite tests passed before production edits. Initial regression batch reproduced 15 failures.

## Progress migration safety

Run `python scripts/audit_progress.py` against the target database before migration. Exit 0 means no duplicates; exit 2 means reconciliation is required. This workspace's tests do not establish whether Neon has duplicates. The migration audits again under an exclusive table lock and refuses to proceed if duplicates exist.

For duplicates: stop writes, take a Neon branch/backup, archive every affected progress row, and compare its counters with the complete `practice_answers` ledger. If the ledger is complete, replay answers in `(answered_at, id)` order using the existing mastery calculation; retain one progress row and the OR of all star preferences. Delete only the archived duplicate rows in that same transaction. If history is incomplete or counters disagree, do not sum blindly (rows may overlap); review the archived rows and choose an explicit reconciliation before proceeding. Re-run the audit. No live reconciliation has been performed by this change.

The forward migration is additive and does not delete data. Downgrade deliberately refuses to destroy override provenance.

## Import merge and deletion

Source JSON remains immutable. Source occurrences retain an imported baseline and a separate map of manual overrides. Import updates the baseline; manual overrides win. Preview reports preserved overrides, upstream conflicts, and suppressed records. Legacy rows have no recoverable original baseline: on first reimport differing editable values are conservatively treated as manual overrides. The incoming JSON becomes the baseline; original historical content cannot be reconstructed from the database alone.

Deleting an imported vocabulary occurrence records a suppression keyed by source ID. Reimport skips it. Canonical items remain, as do progress and persisted practice snapshots. Canonical totals therefore include source-less items, but selection and chapter coverage use existing occurrences. Coverage is occurrence-based for both numerator and denominator. Deleting a book cascades its chapters and occurrences, preserves canonical items and question history; a later explicit book reimport can recreate book occurrences.

Part filters treat JSON numeric `1` and string `"1"` as the same label; null is not a selected part. Blank imported readings remain legal. Vocabulary questions never request readings.
