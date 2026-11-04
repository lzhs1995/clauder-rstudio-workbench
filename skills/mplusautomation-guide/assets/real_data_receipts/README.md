# Real-data swap receipts

One JSON file per real-data run: `<family>__<dataset>__<YYYYMMDD>.json`.
Generate the skeleton with `python scripts/family_registry.py receipt-template <family> <dataset> <route>`.

Only the whitelisted keys in [the swap contract](../../references/family-source-swap-contract.md) are accepted, and each key has a fixed type: objects or arrays placed in a text or count field are rejected.
The family, dataset and route must be registered in `families.json`, and the route must belong to the family.
Only a valid PASS receipt whose code hashes match the current files counts as real-data swap coverage; a FAIL receipt may be kept but never counts.
Do not add estimates, respondent values or IDs, local paths, or descriptive statistics other than counts.
Estimates and the logical-name-to-local-path index stay in the local evidence directory.
