# TODO — pick up here next

Personal worklist after the 2026-05-01 batch (Quality Enhance removal + audio chat fixes + filename sweep).

## 1. Clean up codes

- `atdj/ui/page_main.py`: lots of commented-out blocks left from earlier merges (e.g. the dead `translator.translate(tanda_prompt)` flow around lines 600 to 616, and other `# Original (Tina): ...` markers from the teammate-edit rule). Once teammates have re-synced, prune these.
- `atdj/agent/nodes.py`: the `# planning_mode` commented-out line and the cortina_selector original block are still there per the teammate-edit rule. Same — drop after sync.
- `doc/changes_after_merge.md`: this whole file becomes redundant once everything is merged into main. Either fold the still-relevant entries into a CHANGELOG or delete.
- Unused imports across the modified files: a quick `ruff check` pass would catch any leftovers from the auto-enhance removal.

## 2. Manual test

Things that still need a human in the browser:

- Refresh and confirm the `_renumber_tanda_ids` auto-migration healed any stale playlist (next_tanda should now hit only the immediate next tanda).
- Sanity-check the audio chat fixes against fresh scenarios — the off-topic-during-menu flow, the action-target-vs-descriptive-context fix, the cleaner clarification options.
- Visual confirm the Quality Enhance toggle is gone from the audio settings strip and the layout still looks right with 2 columns instead of 3.
- Listen test: play through one full multi-tanda session, confirm autoplay no longer fires on cold load and that mid-session track-to-track is seamless.

## 3. Methodology graph generation for presentation

For the project presentation:

- Render a clean architecture graph showing: classifier (PLAN / Q&A / ADJUST_AUDIO) -> respective subgraphs.
- For ADJUST_AUDIO specifically, draw the graph as it stands today: `resolve_pending_menu` -> `parse_request` -> (`clarify_node` / `reject_current` / `resolve_targets_node`) -> `measure_reference` -> `compute_adjustments` -> `execute_enhancement` -> `format_reply`. Plus the `emit_cancel` terminal and the `no_targets_node` branch.
- Mention the design intent on the audio side: the user is listening to the current track as the reference, the agent applies a relative correction to upcoming tracks (current is read-only, hence the rejection menu).
- Consider a second graph for the PLAN flow showing `session_init` -> `tanda_planner` (per tanda) -> `cortina_selector` -> `queue_publisher` -> `session_summary`.
- Tools to consider: Mermaid (renders inline in slide decks), Graphviz, or just a hand-drawn diagram in the slides.
