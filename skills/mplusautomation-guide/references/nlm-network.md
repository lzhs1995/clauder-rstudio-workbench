# NLM network gate for Clash Verge

NotebookLM traffic is a host-local prerequisite. A Windows task only needs the
Windows active Clash Verge profile to contain this exact rule. A MacBook task
needs the MacBook active profile to contain it. The other host is not a gate for
RStudio, Mplus or MplusAutomation running on Windows:

```yaml
- DOMAIN-SUFFIX,notebooklm.google.com,链式代理-Gemini
```

The target proxy group must also exist in the profile for the host that will
call NLM. Do not silently replace it with `链式代理`, `US-Trojan` or `DIRECT`:
those are different egress policies. If the group is absent, stop that host's
NLM gate and ask for the intended Gemini chain definition rather than inventing
a node selection.

The checker accepts both native YAML profiles and Clash Verge JSON exports. In
YAML the rule is written with the list marker; in JSON the list value is the
same rule without the marker:

```text
- DOMAIN-SUFFIX,notebooklm.google.com,链式代理-Gemini
DOMAIN-SUFFIX,notebooklm.google.com,链式代理-Gemini
```

## Windows check

Run the checker against the active exported profile, not an old download. If
the profile is missing the group or rule, create an isolated candidate with
`prepare_nlm_clash_profile.py`; do not overwrite the original profile:

```powershell
python skills\mplusautomation-guide\scripts\check_nlm_clash_rule.py `
  --profile "$env:USERPROFILE\...\active-profile.yaml" `
  --platform windows

python skills\mplusautomation-guide\scripts\prepare_nlm_clash_profile.py `
  --source "$env:USERPROFILE\...\active-profile.yaml" `
  --destination "$env:USERPROFILE\...\active-profile_nlm-gemini.yaml" `
  --evidence "$env:USERPROFILE\...\nlm-network-windows.json"
```

The checker verifies the exact rule, the group name and rule ordering. It does
not change Clash Verge state. After a profile update, record the profile hash,
Clash Verge version, active profile name, timestamp and a redacted status/API
probe. A successful browser page alone is not proof of the selected egress.

The provided file `LFMBXcSKOjWk(1)..yaml` is a Windows-local copy of a Mac
profile. With the JSON-aware checker it passes the content check, but it does
not prove that the MacBook is currently running that profile. It is evidence
for a candidate/copy, not active-profile evidence, and it does not block
Windows analysis.

## MacBook check

Run the same checker on the MacBook's active profile only when NLM will be
called from the MacBook, and copy only the redacted JSON evidence into the
project evidence directory. Keep the Mac path and credentials local. The
Windows and Mac checks must be separate records because the two Clash Verge
instances can select different profiles.

## Release rule

The NLM three-pass review is blocked only when the endpoint that will execute
NLM is missing the exact rule, the target group, or a current profile hash.
This network gate is independent of RStudio/Mplus success and is reported as
`nlm_network_status`, with values `PASS`, `BLOCKED` or `UNVERIFIED`. The
candidate profile is not active until Clash Verge imports/selects it and a
fresh profile hash is recorded.
