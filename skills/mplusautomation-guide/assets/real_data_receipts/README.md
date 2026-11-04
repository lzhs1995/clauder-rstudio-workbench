# Real-data swap receipts

One JSON file per real-data run: `<family>__<dataset>__<YYYYMMDD>.json`.
Generate the skeleton with `python scripts/family_registry.py receipt-template <family> <dataset> <route>`.

Only the whitelisted keys in [the swap contract](../../references/family-source-swap-contract.md) are accepted.
Do not add estimates, respondent values or IDs, local paths, or descriptive statistics other than counts.
Estimates and the logical-name-to-local-path index stay in the local evidence directory.
