# Shared AMS reader

This is the canonical React/TypeScript reader for public, portable and explicitly
started local use. `tools/seo_build.py` calls this build; the previous renderer and
root HTML are retired. Source cutover does not imply a main merge or deployment;
see [current state](../../docs/current-state.md).

From this directory:

```sh
npm ci
npm run typecheck
npm run build -- --output /path/to/a/new/public-site
```

Run the repository's content compiler first. `build.mjs` consumes its generated
public projection, emits one body shard per object, and pre-renders the same
React tree that `client.tsx` hydrates. It does not launch a browser or read a
private data root. An existing output directory is refused. `--base
/agent-memory-study/` selects the Pages deployment prefix; `/` is the local
preview default.

The shared body renderer is `src/content.tsx`; only compiler-produced public
HTML enters its HTML rendering path. Imported snapshots, notes and excerpts are
text. `src/exercises.tsx` wraps the established pure teaching engines without
reimplementing their calculations. `src/desk-store.ts` owns pending edits,
acknowledgements, conflicts and history; `src/adapters.ts` distinguishes the
page-only public environment from the explicitly launched local service.

Colours, spacing, typography, responsive states and focus styles are owned by
`src/style.css`. Self-hosted font subsets and their complete notices remain in
the repository's [font source guide](../../assets/fonts/README.md). A desktop
build, a rendered browser check, an installed local environment and a published
site are separate states.
