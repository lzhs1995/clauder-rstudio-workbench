# Recover Windows result exports without repeating estimates

When saved gt/ggplot objects fail with `Total path length must be less than
PATH_MAX: 260`, render to a short local directory and simple filename with the
same extension. Preserve table/plot data, renderer arguments, dimensions and
working directory. For gt use a short `filename` plus explicit `path`; for
ggsave replace `filename` and remove an obsolete `path` argument. Do not solve
an export error by rerunning Mplus.

Archive the previous failure record before publishing. Copy from the short
artifact to the isolated run's intended output using a runtime supporting
Windows extended paths, then compare SHA-256 for the staged file and both
published/archive copies. Record the original render-object hash, output hash,
renderer version and actual destination. Retain a distinct failure if publishing
fails after successful rendering. Validate file content too: PNGs must decode;
DOCX files must contain valid Word XML. Spot-check layout before manuscript use.

Large compressed RDS exports can contain serialized environments much larger
than the image or table. Load one at a time, release the object and collect
garbage between exports. Keep resource checks and mutual exclusion with an
existing foreground estimator. A successful export is not proof that the
model, labels, borrowed footnotes or paper claims are correct.

For headless Chrome, record ownership when this export creates the browser:
PID, creation time and parent R PID. Once its sessions are closed, use that
owned Chromote object's `close()` method and verify exit. Do not close an
already-existing shared browser merely because rendering is idle. Inspect the
installed API before cleanup: the tested Chromote build rejects
`set_default_chromote_object(NULL)`; `has_default_chromote_object()` checks
liveness and the next render can create a new browser after `close()`.

Keep retryable resource waits separate from renderer errors, and use one
dispatcher per output set. Resume from validated recovery records; preserve
failed attempts for review instead of counting every processed item as success.
