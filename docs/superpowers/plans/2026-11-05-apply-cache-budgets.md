# Apply measured SQLite cache budgets and evaluate ORM

User approved the prior per-database raw-pool recommendations. All work local;
no production connection, deployment, source DB writes or database copies.

1. Regression test ordinary pool initial/overflow/replacement handles at 2000 KiB.
   Keep toponyms 4096, GIS 2000, ATTACH schema default 2000, all capacities,
   timeouts, transactions and access permissions unchanged.
2. Change the ordinary pool's shared default from 16000 to 2000 KiB.
3. Evaluate four ORM profiles using real model reads against local mode=ro files
   and synthetic temporary write fixtures. Budgets 2000/4096/8192/16000;
   logs additionally 64000. Three rounds, independent read/write subprocesses.
   No concurrency; each subprocess timeout 60s, read statement progress deadline3s.
   Synthetic fixture12000 rows plus20 bounded batches; vocabulary batches512
   share one transaction. Logs diagnostics20x25 with2KiB body. No retries.
4. Check equal read signatures, row counts, rollback, read-only guards. Report
   timings and RSS limitations. ORM runtime policy changes are recommendations
   at this stage; preserve current ORM pools and write behavior.
5. Run relevant regression suite, request focused review, commit and integrate
   into local dev while preserving unrelated user changes. No push/deploy.
