## Contribution type

- [ ] Source correction / version watch
- [ ] New material + reading note
- [ ] Perspective / critique on an existing entry
- [ ] Public test artifact
- [ ] Reader / accessibility implementation

## What this changes

<!-- Name the material or surface and describe the research value of the change. -->

## Evidence and scope

- Source / public artifact links:
- Version or date checked:
- Reading scope:
- What is source-backed:
- What is editorial inference:
- What remains unverified:

## Constellation / atlas placement, if applicable

- Material ID and stable deep link:
- Failure surfaces added or removed:
- Evidence for each membership:
- Expected cross-surface bridge, if any, and why it is semantically warranted:
- [ ] I updated both the material's `failureSurfaces` and each surface's `materialIds`.
- [ ] I did not add coordinates, rank, importance, star size, manual edges, or a fixed corpus count.
- [ ] The visual depth ring remains derived from the truthful `noteDepth`; I did not add a separate progress or achievement state.
- [ ] If I changed the atlas taxonomy, I explained why the existing failure surfaces could not represent the new boundary.

## Attribution and publication boundary

- Requested public byline:
- [ ] I have the right to submit the text, fixtures, and artifacts in this pull request for public publication in this repository.
- [ ] I have not included private or proprietary data, internal project findings, local paths, private runtime evidence, prompts, sessions, routing evidence, or unpublished personal material.
- [ ] I understand that a project-specific result must identify a public, independently inspectable project and does not automatically generalize beyond it.
- [ ] I have read `NOTICE.md`; I am not assuming that opening this pull request transfers rights or applies an unstated license. Attribution and permission should be confirmed before merge.

## Public test artifact, if applicable

- Method:
- Environment:
- Public / synthetic fixture:
- Raw result:
- Derived result:
- Controls:
- Limitations:
- Reproduction link:

## Validation

- [ ] I edited `data/materials.json`, not generated `assets/materials-data.js`.
- [ ] `python3 tools/build.py`
- [ ] `python3 -m unittest tools.test_build`
- [ ] `python3 research/memprobe-recovery-boundary-audit/verify_checked.py --mode receipt-only`
- [ ] Bundled PDF delivery and notices are unchanged, or each changed file has an explicit redistribution license and attribution.
