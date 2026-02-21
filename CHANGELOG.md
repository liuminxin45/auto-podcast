# Changelog

## [2.4.0] - 2026-02-21

### Dependency Diet: Removed 7 heavy dependencies

- **`pyproject.toml`**: Removed `numpy`, `scikit-learn`, `simhash`, `jieba` — **7 fewer packages** (including transitive deps). Python dependency count: 14 → 10.
- **`simhash`** and **`jieba`**: Were completely unused (zero imports across the entire codebase). Dead dependencies.
- **`numpy`** and **`scikit-learn`**: Only used in `topic_selection/node.py` for TF-IDF + KMeans clustering — replaced with pure-Python implementation.

### Pure-Python Clustering (replaces sklearn)

- **`nodes/topic_selection/node.py`**: Rewrote `_cluster_contents()` using pure-Python TF vectors + cosine-similarity K-Means. No external dependencies. Same clustering quality for the project's scale (~10-100 documents).
- Algorithm: tokenize → build vocabulary (top 100 terms by DF) → TF vectors → L2-normalize → K-Means (max 20 iterations, deterministic init)

### Pipeline Manifest: Artifact Tracking + Resume Support

- **`protocol/manifest.py`** (NEW): `PipelineManifest` class that records per-node completion status, timing, output summaries, and error counts into `state["_manifest"]`.
- **`protocol/node_runner.py`**: `NodeContext.finalize()` now automatically calls `PipelineManifest.record()` — every node completion is tracked without any per-node code changes.
- **`electron/workflowRunner.js`**: Added `resumeFrom='auto'` mode that reads the manifest to auto-detect the first incomplete node and resume from there.
- Manifest data structure: `{created_at, nodes: {<name>: {status, completed_at, elapsed_s, errors, outputs}}, last_node, updated_at}`

### E2E Mock Test Suite

- **`tests/test_e2e_pipeline.py`** (NEW): 20-test E2E suite that runs all 12 pipeline nodes sequentially without external services or API keys.
  - Full pipeline flow: fetch(mock) → manual → merge → preprocess → research → topic_selection → script → tts → audio_postprocess → assets → review → publish
  - Manifest tracking tests: verifies node recording, resume index calculation, error status handling
  - Run: `python tests/test_e2e_pipeline.py`

### UI Simplification

- **`src/components/soundStudio/`** (NEW module): Extracted types (100+ lines) and constants (120+ lines) from `SoundStudio.tsx` into `types.ts`, `constants.ts`, and `index.ts`. Main component reduced by ~300 lines.
- **`SettingsAnalytics.tsx`**, **`SettingsGrowth.tsx`**: Marked as DEPRECATED — orphaned components with zero imports from any file.

### Verification

- 17/17 Python smoke tests pass (`python tests/test_nodes.py`)
- 20/20 E2E pipeline tests pass (`python tests/test_e2e_pipeline.py`)
- TypeScript compiles clean (`npx tsc --noEmit`)
- Zero dangling imports for removed dependencies

## [2.3.0] - 2026-02-21

### Breaking: Removed langchain dependency

- **`nodes/script/node.py`**: Rewrote to use `protocol/llm_client.py` (raw requests) instead of `langchain-openai` (`ChatOpenAI`). Functionally equivalent — same prompts, same JSON parsing, same normalization.
- **`pyproject.toml`**: Removed `langchain>=0.1.0`, `langchain-core>=0.1.0`, `langchain-openai>=0.0.5` — **eliminates 3 heavy dependencies** and their transitive trees.
- **Migration**: If you relied on langchain being installed via this project, install it separately.

### Node Consistency: All 12 nodes now use NodeContext

- **`nodes/fetch/node.py`**: Migrated from manual log/error management (~40 lines boilerplate) to `NodeContext`
- **`nodes/research/node.py`**: Migrated to `NodeContext` — debug_mode and auto_execute now read from ctx
- **`nodes/topic_selection/node.py`**: Migrated to `NodeContext`
- **`nodes/tts/node.py`**: Migrated to `NodeContext`
- **`nodes/script/node.py`**: Migrated to `NodeContext` (part of langchain removal rewrite)
- All 12 nodes now have consistent start/end logging, timing, and error handling via `NodeContext`

### Workflow Runner: Per-node retry

- **`electron/workflowRunner.js`**: Added retry mechanism for retryable nodes (fetch, manual, merge, preprocess, research, topic_selection, script, assets, review). Max 1 retry with 2s delay. TTS, audio_postprocess, and publish are not retried (side effects).
- Retry attempts are logged to workflow state and broadcast to frontend

### Dead Code Removal

- **`electron/main.js`**: Removed 3 legacy `trendradar:start/stop/status` IPC stubs
- **`electron/preload.js`**: Removed 5 legacy trendradar IPC bindings
- **`src/global.d.ts`**: Removed 5 legacy trendradar TypeScript declarations

### Verification

- 17/17 Python smoke tests pass (`python tests/test_nodes.py`)
- TypeScript compiles clean (`npx tsc --noEmit`)
- No dangling imports, no dead references

### Migration Notes

- **`script` node now requires `api_base`** in addition to `api_key`. Previously langchain could default to OpenAI's endpoint; now you must set `api_base` (or `OPENAI_API_BASE` env var) explicitly.
- **`trendradarStart/Stop/Status`** IPC calls are removed. If frontend code used these, it will get "handler not found" errors — but these were already no-ops.

## [2.2.0] - 2026-02-21

### Config Unification (Breaking Internal)

- **`nodes/tts/config.py`**: Migrated `TTSConfig` from `@dataclass` to Pydantic `NodeConfigBase` — now has validation, schema extraction, consistent `from_dict()`
- **`nodes/audio_postprocess/config.py`**: Migrated `AudioPostprocessConfig` from `@dataclass` to `NodeConfigBase`
- **`nodes/assets/config.py`**: Migrated `AssetsConfig` from `@dataclass` to `NodeConfigBase`
- **`nodes/publish/config.py`**: Migrated `PublishConfig` from `@dataclass` to `NodeConfigBase`
- All 12 node configs now use the same Pydantic base class

### Code Deduplication

- **`protocol/dedup.py`** (NEW): Extracted shared `deduplicate_by_title()` function used by both merge and preprocess nodes — eliminates ~40 lines of duplicated logic
- **`nodes/merge/node.py`**: Now uses `protocol.dedup.deduplicate_by_title` instead of local `_deduplicate()`
- **`nodes/preprocess/node.py`**: Now uses `protocol.dedup.deduplicate_by_title` instead of local `_dedup()`

### Bug Fixes

- **`scripts/verify_nodes.py`**: Fixed Windows `UnicodeEncodeError` (gbk codec can't encode emoji) — added UTF-8 output wrapper; increased fetch timeout from 10s→30s; configured offline-only source to avoid network timeouts
- **`scripts/integration_test.py`**: Fixed broken `FetchConfig(sources=[], max_items_per_source=5)` — those parameters don't exist; rewrote as merge→preprocess pipeline test + added review node test
- **`scripts/test_all_nodes.py`**: Added Windows UTF-8 encoding fix
- **`nodes/fetch/test.py`**: Removed non-existent `auto_discover` parameter from `FetchConfig`
- **`nodes/*/test.py`** (8 files): Fixed missing `f`-string prefix in `print_success()` calls
- **`nodes/publish/node.py`**: Added XML escaping (`html.escape`) to all user content in RSS generation — prevents XML injection/malformation

### Security

- **RSS XML escaping**: All user-provided strings (titles, descriptions, paths) in RSS feed output are now properly escaped via `html.escape()`

### Engineering

- **`.env.example`** (NEW): Environment variable template for LLM and TTS credentials

### Testing

- All 12 node smoke tests now pass: `python scripts/test_all_nodes.py` → 12/12 ✅
- All 12 node verifications pass: `python scripts/verify_nodes.py` → 12/12 ✅
- All 3 integration tests pass: `python scripts/integration_test.py` → 3/3 ✅
- Frontend build passes: `npm run build` ✅

### Migration Notes

- **No breaking changes** to external behavior, output formats, or Electron IPC
- Node configs that were `@dataclass` now use Pydantic — `from_dict()` still works identically
- If you had custom code importing `_deduplicate` from merge or `_dedup` from preprocess, import `deduplicate_by_title` from `protocol.dedup` instead

## [2.1.0] - 2026-02-21

### Refactoring & Cleanup

- **`protocol/node_runner.py`**: Added `NodeContext` class — standardized logging/timing helper that eliminates ~20 lines of boilerplate per node
- **7 nodes refactored** to use `NodeContext`: manual, merge, preprocess, assets, audio_postprocess, review, publish
- **`engine/daemon.py`**: Deprecated and replaced with stub — Electron radar service (`runRadarOnce`) provides the same functionality without a separate Python process
- **`electron/main.js`**: Removed ~100 lines of daemon spawn/management code and 3 redundant IPC handlers (`trendradar:start/stop/status` now return stubs)
- **`electron/constants.js`**: Replaced with stub (was never imported anywhere)

### Bug Fixes

- **`nodes/preprocess/node.py`**: Fixed `_dedup()` — was ignoring `similarity_threshold` parameter and doing exact-match only. Now uses `SequenceMatcher` with the configured threshold, consistent with `merge/node.py`

### Configuration

- **`nodes/research/config.py`**: Migrated `ResearchConfig` from raw `@dataclass` to `NodeConfigBase + LLMConfigMixin` — now has Pydantic validation, consistent `from_dict()`, and proper schema extraction
- **`nodes/topic_selection/config.py`**: Migrated `TopicSelectionConfig` from raw `@dataclass` to `NodeConfigBase + LLMConfigMixin` — temperature default preserved at 0.3
- **`protocol/__init__.py`**: Now exports `NodeContext` and `run_node_cli` for convenient imports
- **`config.example.yaml`**: Commented out `subtitles` section (no corresponding node implementation exists)

### Testing

- **`tests/test_nodes.py`**: New comprehensive smoke test suite — 17 tests covering all 12 pipeline nodes plus `NodeContext`. Runs without external services or API keys.
  - Run: `python tests/test_nodes.py` or `python -m pytest tests/test_nodes.py -v`

### Documentation

- **`docs/ARCHITECTURE.md`**: Complete rewrite to match actual codebase — removed references to non-existent files (`orchestrator/graph.py`, `main.py`, `studio.py`, `langgraph.json`), updated directory structure, data flow diagram, state field table
- **`README.md`**: Rewritten with accurate project structure, development commands, testing instructions, and troubleshooting table

### Migration Notes

- **No breaking changes** to external behavior or output formats
- `engine/daemon.py` is now a stub — if you were running `python -m engine.daemon` directly, use `python -m nodes.fetch` with JSON state on stdin instead
- The 3 `trendradar:*` IPC calls still work (return "not running" stubs) so frontend code is unaffected
