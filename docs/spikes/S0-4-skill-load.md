# S0-4 — Skill-load freshness (STATIC ONLY)

Question: do skills load from `<project>/.opencode/skills/<name>/SKILL.md`
and `~/.config/opencode/skills/<name>/SKILL.md`?

Probed on opencode 1.18.21, host Linux, 2026-08-22. **Static scope only**, per
plan: dynamic freshness-across-steps (skill edited mid-session picked up on a
later step) is deferred to P3 E2E.

## Method

Three static checks:

1. `ls` the global dir and confirm `<name>/SKILL.md` files exist on disk;
2. Create a scratch project `/tmp/opencode/s04-skills` with
   `.opencode/skills/probe-skill/SKILL.md` (frontmatter `name` +
   `description`), then run `opencode debug skill` from that cwd — the
   command lists every discovered skill with its absolute source location;
3. Match locations: project probe must resolve under the scratch tree; global
   skills must resolve under `~/.config/opencode/skills/`.

## Transcript

```
$ ls ~/.config/opencode/skills/
fable-domain  fable-judge  fable-loop  fable-method
gauntlet-loop  gauntlet-repo  open-ultracode

$ ls ~/.config/opencode/skills/fable-method/SKILL.md ~/.config/opencode/skills/open-ultracode/SKILL.md
/home/io/.config/opencode/skills/fable-method/SKILL.md
/home/io/.config/opencode/skills/open-ultracode/SKILL.md

$ printf -- '---\nname: probe-skill\ndescription: S0-4 static load probe skill\n---\n\nProbe skill body.\n' \
    > /tmp/opencode/s04-skills/.opencode/skills/probe-skill/SKILL.md

$ opencode debug skill          # cwd = /tmp/opencode/s04-skills; exit=0   (11 skills listed)
63:    "name": "probe-skill",
65:    "location": "/tmp/opencode/s04-skills/.opencode/skills/probe-skill/SKILL.md",

# location histogram across the full listing:
locations under ~/.config/opencode/skills: 7      ← global user skills load
locations under ~/.claude/skills: 2               ← (also loaded, bonus finding)
other locations: ['<built-in>',
                  '/tmp/opencode/s04-skills/.opencode/skills/probe-skill/SKILL.md']
```

Raw output: `evidence/spikes/S0-4-debug-skill-project-and-global.txt`.

Corroboration: all seven global skills appear by name in this opencode
install's own advertised skill list, i.e. they are not merely files on disk
but actively registered.

## Verdict: CONFIRMED(static)-DYNAMIC-DEFERRED

- CONFIRMED (static): both path patterns are real discovery sources —
  `<project>/.opencode/skills/<name>/SKILL.md` (probe found at its exact
  scratch path) and `~/.config/opencode/skills/<name>/SKILL.md` (7/7 global
  skills resolved there). Built-ins also exist (`<built-in>`).
- DEFERRED: whether an edited SKILL.md is re-read on later steps within/across
  sessions is NOT proven here. Deferred to P3 E2E by plan. Until then, treat
  installed skills as write-once artifacts and never rely on mid-run edits.

## Fallback if refuted

None needed for the static claim. If P3 E2E later shows stale caching of
edited skills, the fallback is to bump a version marker in the frontmatter or
reinstall the skill directory rather than editing in place.

## Residual risk

- Dynamic freshness unproven until P3 E2E (explicitly accepted deferral).
- Bonus finding that `~/.claude/skills/` ALSO loads means name collisions with
  Claude-side skills are possible; our roster names are unique enough today.
