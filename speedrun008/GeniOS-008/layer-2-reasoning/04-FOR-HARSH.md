# L2 Reasoning — for Harsh

**Written for:** Harsh, who deploys and runs production. **Started:** 18 Oct 2026. Each pushed group of L2 work
adds a section at the bottom.

## 1 · What is happening to L2, in one paragraph

Today L2 (`reason/` + `packs/`) mostly decides by formula and rule:
- 23 deterministic reasoners score risk, priority and confidence;
- the pack rules fire;
- an optional LLM decider picks between the candidates.

The new architecture and Rohit's L2 spec make the **LLM the reasoning engine**:
- one bounded judgment pass per situation reads the signals, the company context, the history and the domain expertise;
- it returns a structured `ReasoningResult`: facts, inferences, hypotheses, unknowns, framing, consequences, options, next move and confidence per dimension;
- deterministic code only supports it: retrieval, IDs, permissions, exact numbers.

The STEP-12 expert pass is the starting point; it already works this way for *files*. The plan is
[`02-PLAN.md`](02-PLAN.md).

## 2 · What changes for you, and when

| When | What you will do | Why |
|---|---|---|
| **Now** | nothing new for L2 | No L2 code has changed yet |
| **Before any L2 work reaches production** | the Layer 1 deploy (`../layer-1-enterprise-signals/04-FOR-HARSH.md` §4 H1) | Production still runs `harsh/mvp`, 815+ commits behind |
| **Each L2 group pushed** | follow its section below: migration (if any), flag, what to watch, rollback | The new path runs **in shadow** first: it writes its own tables and changes no card |
| **The first switch** (awaiting reply / outreach) | turn one flag on for Rohit's org only; watch for one day; the steps will be written here | Only switched after the golden set shows the new path is at least as good |

## 3 · Things to have ready (read only, nothing to change yet)

1. **The value of `GENIOS_L4_LLM_DECISION_MAKER` in production.** The LLM decider will be retired. We need to know if it is on today.
2. **Whether `expert_review` is activated for Rohit's org** after the deploy (`08` §0.5). The new judgment pass grows out of it.
3. **The model key and spend limits.** The judgment pass runs Sonnet-class, about $2 a day for Rohit's org (as STEP-12). Any change will be written here before it ships.
4. **Database load.**
   - L2 currently opens two transactions per situation (`reason/audit.py:283` + `domain_shadow._persist_live`).
   - The new path batches them, one per sweep (plan unit L2-G1).
   - Expect the transaction count in the `DATABASE_LOAD_ANALYSIS` to fall once the switch happens, not before.

## 4 · How each switch will be written for you

Every switch section below will have these parts:
- **What changed:** files and behaviour, in plain words.
- **Migration:** number, what it adds, whether it can be re-run.
- **Flag:** name, which org, how to turn it on and off.
- **Run:** the exact commands.
- **You should see:** tables, counts, log lines.
- **It went wrong if:** the symptoms, and what to send back.
- **Roll back:** one line.

---

## Sections per pushed group

*(none yet. L2 is planned, not built.)*
