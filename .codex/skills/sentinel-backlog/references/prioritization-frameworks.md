# Prioritization frameworks — a coaching reference

This is an **educational menu**, not a mandate. Ignite Sentinel governs the backlog and its ordering signals (SLICE-PLAN waves, readiness scores, dependencies, enabler boundaries); it does **not** auto-prioritize value stories or pick a method for the BA. When a BA/Product owner is deciding *what to build first*, use this to surface the options and their trade-offs in the coaching posture (see the maturity/health skills' `## Adaptive Decision Ladder`). **The BA chooses the frame.**

Two rules cut across every framework below:

- **Inputs must rest on evidence.** Reach, impact, effort, importance, and satisfaction are only as trustworthy as their sources. Anchor each number in cited local evidence or an explicit, recorded assumption — never an invented score that only looks rigorous.
- **A framework ranks; it does not decide.** These are lenses to make a trade-off legible. The decision, and the accountability for it, stays with the BA.

---

## 1. MoSCoW — Must / Should / Could / Won't

- **Optimizes for:** a shared, categorical agreement on scope for a fixed timebox or release.
- **Inputs:** each item sorted into Must (release fails without it), Should (important, not vital), Could (nice-to-have), Won't (explicitly out, this time).
- **Reach for it when:** aligning stakeholders on release scope, especially with a hard deadline.
- **Trap:** "Must" inflation — everything becomes a Must and the frame loses meaning. Cap the Must list and make "Won't" explicit (it pairs naturally with governed Non-Goals).

## 2. Kano Model — Basic / Performance / Delighter

- **Optimizes for:** understanding how a feature affects *satisfaction*, not just its raw value.
- **Inputs:** classify each feature as Basic (absence causes dissatisfaction, presence is expected), Performance (more is linearly better), or Delighter (unexpected, disproportionate delight). Ideally informed by user signal.
- **Reach for it when:** the debate is "is this table-stakes or a differentiator?".
- **Trap:** categories drift over time — today's Delighter becomes tomorrow's Basic. Re-classify periodically; don't treat it as permanent.

## 3. RICE — (Reach × Impact × Confidence) ÷ Effort

- **Optimizes for:** a comparable score across many candidates using four explicit factors.
- **Inputs:** Reach (how many, per period), Impact (per-user effect, often a 0.25–3 scale), Confidence (a % discount for uncertainty), Effort (person-time). Score = R × I × C ÷ E.
- **Reach for it when:** you have a long list and want a defensible, sortable ranking.
- **Trap:** false precision — the score inherits every guess in its inputs. Confidence is the honesty valve; if it's low, the ranking is a hypothesis, not a verdict.

## 4. ICE — Impact × Confidence × Ease

- **Optimizes for:** a fast, lightweight first-pass ranking.
- **Inputs:** Impact, Confidence, Ease, each scored (e.g. 1–10). Score = I × C × E.
- **Reach for it when:** triaging quickly, or ranking experiments where precision isn't worth the effort.
- **Trap:** highly subjective and scorer-dependent. Use it to sort a shortlist, not to justify a big irreversible bet.

## 5. WSJF — Weighted Shortest Job First (SAFe)

- **Optimizes for:** economic sequencing — maximizing value delivered per unit of time.
- **Inputs:** Cost of Delay (user/business value + time criticality + risk-reduction/opportunity-enablement) ÷ Job Size. Highest first.
- **Reach for it when:** sequencing a flow of work where delay has a real, differing cost per item.
- **Trap:** estimating Cost of Delay is hard and easy to hand-wave. Use relative (Fibonacci-style) estimates across items rather than pretending to absolute currency values.

## 6. Value vs Effort — the 2×2

- **Optimizes for:** a quick visual triage into Quick Wins, Big Bets, Fill-ins, and Money Pits (time sinks).
- **Inputs:** each item placed on two axes — value (high/low) and effort (high/low).
- **Reach for it when:** you need a fast, communicable picture for a workshop.
- **Trap:** two axes hide nuance (risk, dependencies, confidence). It's a conversation starter, not the final ranking.

## 7. Opportunity Scoring — Outcome-Driven Innovation (Ulwick)

- **Optimizes for:** finding under-served needs: important *outcomes* that customers are dissatisfied with.
- **Inputs:** for each desired outcome, its Importance and current Satisfaction (survey-based). Opportunity = Importance + max(Importance − Satisfaction, 0).
- **Reach for it when:** deciding where to invest for differentiation, grounded in customer outcomes rather than feature requests.
- **Trap:** needs real customer data; guessed importance/satisfaction produces confident nonsense. High-importance + high-satisfaction = already served (don't over-invest).

## 8. Cost of Delay / CD3 — Cost of Delay Divided by Duration

- **Optimizes for:** making the economic cost of *not* shipping visible, and sequencing by it.
- **Inputs:** Cost of Delay per item (value lost per unit time waiting) ÷ Duration. Highest CD3 first. (WSJF is the SAFe-flavored relative form of this idea.)
- **Reach for it when:** time-sensitive value is the dominant factor — deadlines, market windows, regulatory dates.
- **Trap:** teams quote effort but rarely quantify delay cost. The insight is in *asking* "what does a month of delay cost?", even qualitatively.

## 9. Story Mapping (Jeff Patton)

- **Optimizes for:** sequencing and slicing along the user's journey, so each release is a coherent thin slice end-to-end.
- **Inputs:** the backbone of user activities left-to-right; stories arranged top-to-bottom by priority under each; horizontal "release slices" cut across.
- **Reach for it when:** planning a first release or an MVP and you want walking-skeleton coverage rather than a deep silo.
- **Trap:** it organizes and slices but doesn't score — pair it with a scoring frame (RICE/WSJF) when you need to choose *between* competing slices. It complements Ignite's INVEST/SPIDR/Lawrence slicing model, it doesn't replace it.

---

**Choosing a frame (coaching cues):**

- Fixed deadline, scope debate → **MoSCoW**.
- Table-stakes vs differentiator → **Kano**.
- Long list, want a defensible sort → **RICE** (or **ICE** for a fast first pass).
- Delay has real, differing cost → **WSJF** / **Cost of Delay**.
- Need a quick shared picture → **Value vs Effort 2×2**.
- Investing for differentiation from customer outcomes → **Opportunity Scoring**.
- Planning a coherent first release → **Story Mapping**.

No framework substitutes for the evidence discipline: if the inputs aren't grounded, neither is the ranking.
