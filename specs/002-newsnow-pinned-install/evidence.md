# Evidence: NewsNow 固定版本安装与自定义采集能力部署

## Environment

- Date: 2026-06-25
- Branch: `002-newsnow-pinned-install`
- Node: `v23.9.0`
- NewsNow locked commit: `290f1a67da745d77e4ed23eb096f6ad7d8f0322e`
- NewsNow locked version: `0.0.40`

## Command Evidence

### `npm install`

- Result: PASS
- Evidence:
  - postinstall executed `sync_trendradar.py`
  - postinstall executed `sync_newsnow.py`
  - `sync_newsnow.py` reported locked ref `290f1a67da745d77e4ed23eb096f6ad7d8f0322e`
  - `sync_newsnow.py` reported `Applying overlay: auto-podcast-custom-sources`
  - `newsnow_runtime.js setup` returned `success:true`
  - `overlayApplied:true`
  - `dependenciesInstalled:true`

Non-blocking warnings:

- `npm warn EBADENGINE` for `eslint-visitor-keys@5.0.1` on Node `v23.9.0`.
- Missing local extra cert path `D:\UserData\Desktop\tp-link-CA.crt`.

### `npm run sync:newsnow`

- Result: PASS
- Output summary:
  - target: `E:\Neo\auto-podcast\engine\newsnow`
  - locked version: `0.0.40`
  - locked ref: `290f1a67da745d77e4ed23eb096f6ad7d8f0322e`
  - existing checkout already at locked ref
  - overlay applied: `auto-podcast-custom-sources`

### `npm run check:newsnow`

- Result: PASS
- Status assertions:
  - `success:true`
  - `available:true`
  - `lockedCommit == localCommit == 290f1a67da745d77e4ed23eb096f6ad7d8f0322e`
  - `packageVersion:"0.0.40"`
  - `nodeCompatible:true`
  - `pnpmAvailable:true`
  - `dependenciesInstalled:true`
  - `built:true`
  - `overlayApplied:true`
  - `overlayErrors:[]`
  - `blocker:""`

### `npm run verify`

- Result: PASS
- Output summary:
  - `verify:config`: 3/3 passed
  - `verify:nodes`: 12/12 passed
  - `verify:trendradar-settings`: passed

Accepted warnings:

- `topic_selection` fixture reports no content.
- `script` fixture reports missing topic/materials.
- Both are existing fixture-level warnings and the command reports all nodes passed.

### `npm run build:newsnow`

- Result: PASS
- Status assertions:
  - `success:true`
  - `built:true`
  - `overlayApplied:true`
  - `overlayErrors:[]`

Accepted warning:

- Upstream `scripts/favicon.ts` logged `autopodcast: error downloading the image. fetch failed` with `read ECONNRESET`.
- The command exited 0 and Nitro server build completed successfully.

### `npm run build`

- Result: PASS
- Output summary:
  - `tsc` passed
  - Vite production build completed
  - assets emitted under `dist/`

Accepted warning:

- Existing Vite chunking warning for `llmService.ts` dynamic/static import mix.

## Repository Boundary Evidence

Parent repository `git status --short --branch`:

```text
## 002-newsnow-pinned-install
 M .specify/feature.json
 M engine/newsnow.lock.json
 M package.json
 M scripts/newsnow_runtime.js
 M scripts/sync_newsnow.py
?? engine/newsnow-overlays/
?? specs/002-newsnow-pinned-install/
```

`engine/newsnow/` is ignored by the parent repository and is not a commit target.

NewsNow sub-repository dirty files after overlay/build:

```text
 M server/glob.d.ts
 M shared/pinyin.json
 M shared/pre-sources.ts
 M shared/sources.json
```

These are Auto-Podcast managed overlay patch targets or NewsNow generated files listed in `engine/newsnow.lock.json`.
