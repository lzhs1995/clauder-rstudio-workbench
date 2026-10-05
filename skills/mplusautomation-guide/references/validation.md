# Model and manuscript validation

For every task, retain the input `.inp` hash, output hash, Mplus exit/finish
state, warning list, parameter count, and SAVEDATA checks. Recompute hashes
from disk and compare them with queue records. Summarize results in a model
audit table with `PASS`, `REVIEW`, or `FAIL`.

For every manuscript table, record the expected model set and row count, the
generated estimates available, the historical/reference estimates available,
and an explicit discrepancy reason. Validate Appendix rows separately. Do not
declare full reproduction while any required table remains blocked, incomplete,
or only supported by an unreviewed historical output.
