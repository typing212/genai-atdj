# Future Work — AT-DJ v2 Roadmap

## Answer Summary
Five ideas captured during v1 development that are not shipping in this submission. Each addresses a real tango-DJing concern — vocabulary grounding, live floor reactivity, a user-extensible catalog, mode-aware tanda rules, and the agent's ability to explain its own in-session decisions — and is documented here as a v2 roadmap entry with a brief description, feasibility note, and the change it would bring once integrated.

## Key Takeaways
- **Mood calibration** would ground each user's mood vocabulary in actual listening so phrases like "more dramatic" mean what the user thinks they mean.
- **Feedback interrupt** would turn the agent into a live floor-reactive DJ that replans on the fly with a safe fallback.
- **Music upload** would let users grow the catalog at runtime — essential because every tango DJ has their own rare collection.
- **Planning-mode toggle** would support both traditional and alternative milongas, and require the agent to justify any tanda-rule break.
- **In-session Q&A grounding** would let the agent explain its own recent decisions ("why did you pick this cortina?"), which today's Q&A path cannot answer reliably.

---

## 1. Onboarding Mood Calibration Flow

**What it is.** A short, optional onboarding screen shown at session start. The user listens to a few sample tracks spanning the mood and energy spectrum and tags each one with feeling labels (or types their own). The system then uses those labels as a personal reference frame so it can interpret later vocabulary like "more dramatic" or "calmer" the way this particular user means it.

**Feasibility.** Medium. The UI itself is straightforward — a new screen with audio playback and a card-picker. The harder part is curating the reference tracks carefully enough that the mood spectrum lands consistently for tango listeners; a poor track selection would produce noisy calibration data that hurts more than it helps. The pathway from the user's tagged labels into the agent's interpretation step is small in scope.

**Influence once integrated.** Closes the long-standing vocabulary gap between user and agent. Today the agent has to guess what each user means by mood words, and tango mood vocabulary is highly personal — what one dancer hears as dramatic, another hears as routine. With calibration, the agent interprets each phrase against an explicit personal baseline, which improves trust on the very first chat-driven adjustment rather than after several clarification round-trips.

---

## 2. Feedback Interrupt & Race-to-Deadline Replanning

**What it is.** A way for the user to signal mid-session that the floor needs more energy, less energy, a different orchestra, and so on. The agent immediately starts a fresh plan in the background and races it against the playback clock. If the new plan finishes before the next tanda would naturally start, it replaces the upcoming tanda; if it doesn't finish in time, the original plan keeps playing as a safe fallback. The user is notified whenever the upcoming tanda changes and can also jump straight into the new tanda instead of waiting for the natural cortina cut-off.

**Feasibility.** Hard. The data model and the routing slot for this exist in the current code — they were drafted in v1 but never wired to a real UI surface or a real replan path. Actually shipping it requires the planning loop to run asynchronously, a coordinator that compares the replan finish time against the playback deadline, and a UI state machine that tracks "replan in progress", "replan adopted", and "replan missed deadline". None of those pieces exist today. The biggest unknown is concurrency: the user might be mid-cortina when the replan completes, and the system has to handle that without dropping audio.

**Influence once integrated.** Turns the system from a one-shot planner into a live, floor-reactive DJ — the closest behaviour to a human DJ adjusting a milonga in real time. Without it, the user can only react by manually editing the playlist or sending a brand-new plan request, which breaks the live-DJ illusion. With it, the system stops being a planning tool and starts being a DJ assistant.

---

## 3. User Music Upload & On-the-Fly Feature Extraction

**What it is.** A file-upload widget in the UI. When the user drops in a music file, the system saves it, runs the audio-feature extraction pipeline on it, fills in metadata from the file's tags, and adds the new track to both the catalog and the search index — all without requiring the user to re-run any batch process. Cortinas would go through a simpler upload flow because they don't carry orchestra or singer metadata.

**Feasibility.** Medium. Per-track feature extraction already works in v1, so the slow part of the pipeline is solved. The piece that needs new work is making the search index accept incremental additions instead of requiring a full re-ingest from scratch. Style detection from file metadata alone (tango vs vals vs milonga vs cortina) is unreliable, so the upload screen should ask the user to pick the style explicitly rather than guessing.

**Influence once integrated.** Makes the catalog user-extensible, which is essential for any production use. Tango DJs differentiate themselves through rare and personally curated recordings — private rips of out-of-print pressings, recent reissues, niche orchestral editions — and a fixed catalog cannot serve them. Without upload support the system is stuck at whatever was ingested up front, which is fine for a demo but not for a working DJ over many seasons.

---

## 4. Convention vs Flexible Planning Mode

**What it is.** A user-controlled toggle on the session that switches between two milonga conventions. **Convention mode** enforces the traditional tanda rules: every track in a tanda shares the same orchestra, the same singer, and the same era. **Flexible mode** allows the agent to break these rules — mixing orchestras, crossing decades — but only if it can justify the break in writing on the tanda itself. The user reads the justification and decides whether to keep the tanda or replan it. Style (tango, vals, milonga) stays a hard rule in both modes; no mixing those.

**Feasibility.** Medium. The toggle and the user-visible behaviour are simple. The real work is building the rule-checking layer that this project was originally supposed to have but never actually wrote. A previous attempt added the toggle without the validator behind it, which is why it was removed during the recent cleanup. A clean re-attempt needs both halves to land together — the toggle is meaningless without the validator, and the validator is invisible to the user without the toggle.

**Influence once integrated.** Lets the system serve both audiences a tango DJ encounters — the traditionalist crowd that expects strict conventions and the alternative crowd that wants creative connections across orchestras and eras. Without the mode, the system silently falls between the two: nothing strictly enforces convention, and nothing meaningfully enables flexibility. The "rationale required to break a rule" pattern in flexible mode is also a useful design signal in its own right; it surfaces the agent's reasoning to the user instead of letting the LLM silently deviate.

---

## 5. In-Session Q&A — Recent-Context Grounding

**What it is.** Today's Q&A path answers tango knowledge questions by retrieving from a curated knowledge base and Wikipedia. It does not have reliable access to what the agent itself just did in this session — for example, why a particular cortina was selected, why the planner picked one orchestra over another, or why the audio adjustment ended at a particular value. Recent-context grounding would feed the recent activity log and the agent's own decisions into the Q&A retrieval step, so questions like "Why did you choose this cortina?" or "Why did you skip that track?" come back with the actual reason rather than a generic guess.

**Feasibility.** Medium. The activity log is already structured per session and each agent decision carries enough context (selected tracks, chosen cortina, adjustment parameters) to answer from. Wiring it into Q&A is a focused piece of work: detect when a question refers to an in-session decision, pull the relevant log slice, and pass it as context to the answer generator. The harder parts are detecting the question type reliably (so general tango questions don't get diluted with internal session state) and surfacing the right level of detail — a user-facing reason, not a debug dump.

**Influence once integrated.** Closes a transparency gap. Without it, the agent has no grounded answer when a user asks why it made a particular choice — it either hedges or guesses. With it, the agent can explain its own decisions, which is exactly the kind of transparency a tango DJ would expect from an assistant ("I picked this cortina because it contrasts in tempo with the Pugliese tanda you just heard"). It also takes one risky question off the demo's avoid list — today the recommendation is to skip "Why did you choose this cortina?" on stage because the answer is unreliable; with grounding in place, that becomes a feature, not a risk.
