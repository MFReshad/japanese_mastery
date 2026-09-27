# Local synthetic performance results

PostgreSQL 16 in Docker; 2,000 vocabulary occurrences in one chapter. TestClient wall time includes HTTP dispatch. These are local measurements, not Neon latency estimates.

| Operation | Median ms | First/warm SQL statements |
|---|---:|---:|
| Books | 1.00 | 1/0 |
| Chapters | 0.91 | 1/0 |
| Library (50 rows) | 4.87 | 1/1 |
| Study (2,000 rows) | 19.02 | 1/1 |
| Practice start (10) | 5.03 | 3/3 |
| Reveal (durable) | 2.54 | 1/1 |
| Save correct | 5.77 | 7/7 |
| Save wrong | 5.81 | 7/7 |
| Progress / Home statistics | 1.05 | 1/0 |
| Chapter coverage | 0.97 | 1/0 |

`ORDER BY random()` plan for this fixture:

```text
Limit  (cost=8.29..8.30 rows=1 width=12) (actual time=0.333..0.334 rows=10 loops=1)
  Buffers: shared hit=43
  ->  Sort  (cost=8.29..8.30 rows=1 width=12) (actual time=0.332..0.332 rows=10 loops=1)
        Sort Key: (random())
        Sort Method: top-N heapsort  Memory: 25kB
        Buffers: shared hit=43
        ->  Index Only Scan using ix_vocab_sources_book_chapter_order on vocabulary_sources  (cost=0.27..8.29 rows=1 width=12) (actual time=0.033..0.240 rows=2000 loops=1)
              Index Cond: (book_id = '2'::smallint)
              Heap Fetches: 2000
              Buffers: shared hit=43
Planning:
  Buffers: shared hit=5
Planning Time: 0.033 ms
Execution Time: 0.339 ms
```

No replacement for random ordering or additional performance indexes is justified by this fixture. Measure real Neon plans before changing either.
