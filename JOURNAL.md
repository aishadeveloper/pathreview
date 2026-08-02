## Pathreview: Choose Your Issue

## Issue Selected
- Issue #28: Generator produces duplicate feedback sections when a user has multiple projects in the same tech stack.

## Week 7 — Issue selection

**Issue link:** https://github.com/ascherj/pathreview/issues/28

**Issue title:** Generator produces duplicate feedback sections when a user has multiple projects in the same tech stack

**Tier:** [ ] Tier 1  [ ] Tier 2  [✅] Tier 3

**Problem summary:**
The generator produces nearly identical "skills" feedback for each project when a user has several projects built with the same technology — for example, three Python RAG projects. Instead of recognizing that the observation is shared and giving one consolidated piece of feedback, it repeats similar feedback for each project, so the review reads as repetitive and padded. A successful fix would make the generator deduplicate and consolidate these cross-project observations — stating a shared skill once and attributing it to all the projects it applies to — so the review feels distinct rather than repetitive. The affected code lives in `rag/generator/review_generator.py` and `rag/generator/output_parser.py`.

**Branch name:** fix/28-generator-duplicates

**Setup confirmation:** [✅] App runs locally at localhost:5173

**Cohort ledger:** [✅] Issue added to cohort ledger

## Is This Issue Right for Me?
I selected this as a Tier 3 (advanced / AI-system) issue, and I'm comfortable taking it on: I was able to trace the root cause in the codebase before starting, so I know where the fix lives. The scope is well-bounded — the change is contained to two files in the RAG generation layer (`review_generator.py` and `output_parser.py`) rather than rippling across the app — and the core defect is already identified: a `_consolidate_feedback` method that never actually consolidates. The estimated effort (~7–10 hours per the issue) fits the Module 3 timeline. There is one other person working on this issue, but I will be able to implement, test, and submit a PR by the Week 9 deadline, and I don't see any blockers.

## Design Note — Deduplicating cross-project feedback

**Goal (per the issue):** deduplicate and *consolidate* cross-project
observations — say a shared skill once, attributed to all the projects it
spans — rather than generating distinct per-project feedback. Consolidation,
not differentiation.

**Why it happens today.** Reviews are generated per *section*
(`skills_feedback`, `projects_feedback`, …) in `generate_full_review`, not
per project. `generate_section` flattens every project's chunks into one
`{context}` blob and passes only `project_count` (an integer) and
`github_username` to the prompt. The model sees three similar Python projects
side by side, with no project boundaries and no instruction to consolidate,
so it comments on each independently. The existing `_consolidate_feedback`
method is a no-op: its docstring promises to "merge feedback for the same
project," but it only deduplicates by `section_name` (which is already
unique), so it never inspects content or projects.

**What identifiers are available.** At generation time each chunk's metadata
carries only `source_id`, `chunk_index`, and `section` — the richer
per-project metadata (`primary_language`, `repo_name`, `tech_stack`) computed
in `repo_analyzer.py` is dropped by `vector_store.add_chunks`. So `source_id`
is the reliable project key to group on.

**Approach — prevention plus cure, across the two files:**

Layer 1 (prevention, `review_generator.py`): make the generator
project-aware. Group retrieved chunks by `source_id` in `_format_context`,
emit them under explicit `=== Project: <source_id> ===` headers, and pass a
project inventory into the prompt. Update the `skills_feedback` template so
each observation is tagged with the projects it applies to
(`key_skills: list of { skill, evidence, projects: [ids] }`) and instruct the
model: when a skill applies to multiple projects, emit ONE entry listing all
of them instead of repeating it per project. This removes most repetition at
the source.

Layer 2 (cure, `review_generator.py` + `output_parser.py`): implement a real
`_consolidate_feedback` as a post-processing safety net that merges
observations describing the same skill and unions their project lists. This
needs structured input, which is currently blocked in the parser:
`_parse_json_output` fans one response out into one section per top-level JSON
key, and `generate_section` then keeps only `sections[0]`, dropping the rest.
So `output_parser.py` must preserve the structured per-observation shape
(skill + evidence + projects) for consolidation to operate on. Start with
normalized exact-match merging on the skill name; upgrade to lexical or
embedding-based near-duplicate clustering (an embeddings provider already
exists in `ingestion/embeddings/provider.py`) only if the model still varies
its phrasing.

**Caveats to note, not fix here:** the orchestrator only analyzes the first
repo (`break  # Only process first repo for now` in `_build_plan`), and
`add_chunks` persists only `source_id`/`chunk_index`/`section` — both limit
how much per-project signal reaches the generator, but neither blocks this
work.

## Week 8 — Reproduction & solution planning

**Reproduction commit link:** https://github.com/aishadeveloper/pathreview/commit/5897c749a237e0901142e35673ca3ae377b990a1

**Reproduction summary:**
I reproduced the issue deterministically with unit tests in
`tests/unit/test_review_generator.py`: two `xfail(strict=True)` tests feed
`_consolidate_feedback` (and, via a mocked LLM client, `generate_full_review`)
near-identical skill observations attributed to three same-stack projects and
assert they get consolidated — both fail today, and a passing characterization
test confirms `_consolidate_feedback` returns its input unchanged because it
only deduplicates by `section_name`, which is already unique per section.

**PLAN.md link:** https://github.com/aishadeveloper/pathreview/blob/fix/28-generator-duplicates/PLAN.md

**Walkthrough video (recommended):** Not recorded this week.

**Blockers or open questions:**
- 53 unit tests fail on this branch *before* my changes (verified by running
  the suite with and without my commit — same 53 either way, e.g.
  `test_json_array_fallback`, `test_tech_detector` exclusions). I'll diff
  failure lists rather than counts in Week 9 so they don't mask regressions.
- Before changing the parser's return shape I need to trace who consumes
  `generate_section`'s output in `core/services` — the `sections[0]`
  truncation might be load-bearing for non-skills sections.
- A live end-to-end multi-project reproduction is limited by the
  orchestrator's first-repo-only `break`; if I record the walkthrough against
  the running app I'll need seeded multi-project data.

## Week 9 — Solution building & PR submission

### Check-in 1 (mid-week)

**Current progress:**
PLAN.md sub-tasks 1–3 are implemented: `_format_context` now groups chunks
under `=== Project: <id> ===` headers with a project inventory passed to the
prompt, a `v2` `skills_feedback` template instructs the model to emit one
entry per skill with a `projects` list, and `parse_section_output` preserves
the full structured payload that the old `sections[0]` fan-out was dropping.
Confirmed before starting that `core/services` never calls `ReviewGenerator`
(its RAG step is a placeholder), which retired the biggest risk in PLAN.md.

**Next steps:**
Implement the real `_consolidate_feedback` merge (sub-task 4), flip the Week 8
xfail reproduction tests and add edge-case coverage (sub-task 5), then
self-review against docs/CONTRIBUTING.md and open the PR.

**Blockers:**
The repo's pre-commit mypy hook (`disallow_untyped_defs`) checks whole files,
so extending the legacy test files requires annotating their existing
untyped methods — mechanical but it inflates the diff slightly.

---

### Check-in 2 (end of week)

**PR link:** https://github.com/ascherj/pathreview/pull/573

**Branch:** `fix/28-generator-duplicates`

**What you built:**
A two-layer fix for issue #28: the skills prompt now sees explicit project
boundaries and a consolidation instruction (prevention), and
`_consolidate_feedback` genuinely merges `key_skills` entries whose
normalized skill names match, unioning their project lists (cure). A shared
skill is now stated once and attributed to every project that demonstrates
it, instead of being repeated per project.

**Tests added or updated:**
`tests/unit/test_review_generator.py` (Week 8's xfail reproduction tests now
pass with markers removed, plus new coverage for project grouping, merge
normalization, different-observations-not-merged, single-project no-op, and
plaintext fallback), `tests/unit/test_output_parser.py` (new
`parse_section_output` suite), `tests/unit/test_prompt_templates.py` (v2
template and version selection). Unit suite: 396 passed; the 53 pre-existing
failures are byte-identical before and after my changes (failure lists
diffed, not counted).

**Self-review confirmation:** [x] make check passes  [x] make test-unit passes
(both in the documented sense for this codebase: repo-wide pre-existing
failures exist and are listed in the PR; my changes introduce no new
failures, and all touched files pass ruff, black, and mypy.)

**Draft PR feedback received from:** none yet — review requested from an AI
mentor; will also share the PR in the cohort Slack channel.
