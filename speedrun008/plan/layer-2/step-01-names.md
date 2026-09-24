# L2-1 · Name it, and make every name answer one question

**Needs Harsh:** no · **Migration:** none · **Model calls:** none · **Risk:** lowest in the plan

---

## 1. Premise

Three names in this layer are ambiguous, and each one has already cost something measurable.

| name | the problem | what it cost |
|---|---|---|
| `BusinessSituationObject` | **two classes, one name** — `domain_expertise.py:405` and `situation.py:551` | cost this plan's first draft a wrong paragraph: it recorded them as rival duplicates with *"zero callers"* when they are candidate → admitted, joined at `situation_publisher.py:464` |
| "Context Intelligence" | says *where* the layer sits, not *what it does* | L2 has been described as a graph builder for so long that a card was wired to a signal without anyone noticing the situation layer was bypassed |
| layers **3** and **4** for D and R | a digit implies a pipeline position | D and R are not stages — they are what L2 reasons *with*. The numbering has already changed twice; `LAYERS.py` was written to survive that |

⛔ **`LAYERS.py` states the rule this step obeys:**

> *"Package names carry semantics, never digits: the numbers have already changed twice across specs
> while the code did not, so no digit ever appears in a package name."*

---

## 2. Units

### L2-1-U0 · Measure the ambiguity before renaming
Count every import of each `BusinessSituationObject` and record which one it resolves to. A rename
that surprises an importer is a rename done blind.

```
verify:  grep -rn "BusinessSituationObject" genios_engine | wc -l      # baseline, recorded
```

### L2-1-U1 · `SituationCandidate` — renamed at its DEFINITION
`contracts/domain_expertise.BusinessSituationObject` → **`SituationCandidate`**.

⛔ **At the definition, not at one import line.** `situation_publisher` already aliases it
`LegacySituation` at its own import — which fixes the ambiguity in exactly one file and nowhere
else. Every other reader still sees the ambiguous word.

Keep `BusinessSituationObject = SituationCandidate` as a deprecated alias for one release so no
importer breaks, and **mark it deprecated in the docstring with the date it may be removed.**

```
verify:  pytest tests/ -q -p no:randomly          # zero new failures
         grep -rn "BusinessSituationObject" genios_engine/contracts/domain_expertise.py
```

### L2-1-U2 · `LAYERS.py` — Situation Intelligence, Plane D, Plane R
Docstring only. `context` = **Situation Intelligence**. `packs` = **Plane D · Domain Expertise**.
`reason` = **Plane R · Reasoning**. The `LAYERS` dict itself does not change, because the topology
test reads it and the topology is correct.

```
verify:  pytest tests/test_layer_topology.py -q    # must stay green, untouched
```

### L2-1-U3 · A totality guard on the two situation types
The repo idiom — a table with a row per member and an import-time check. Here: **a test that fails
if a third type named `*SituationObject` is ever added without a row explaining which stage it is.**

The ambiguity cost a wrong paragraph once. A guard is what stops it costing a wrong decision later.

```
verify:  pytest tests/context/test_situation_types_are_named.py -q
```

### L2-1-U4 · `docs/LAYER_MAP.md`
The second and last file carrying digits. Update it, and nothing else.

---

## 3. Cost check

| | |
|---|---|
| prompt | unchanged |
| `vocabulary_fingerprint` | **`a3d5496aa0d3`** — must be unchanged, and the test proves it |
| model calls | none |
| migration | none |
| re-extraction | **none** |

---

## 4. What this step does NOT do

* **It does not rename files.** `situation_bso.py` and `situation_publisher.py` keep their names —
  renaming a working file to match a doc is churn, and the doc is what was wrong.
* **It does not change the topology.** `LAYERS` keeps its dict; only prose moves.
* **It does not remove the old name.** A deprecated alias ships for one release with a removal date.

---

## 5. Completion criteria

1. `SituationCandidate` is the name at the definition, and the alias is marked deprecated with a date.
2. `LAYERS.py` and `docs/LAYER_MAP.md` read Situation Intelligence / Plane D / Plane R.
3. A guard refuses a third ambiguously-named situation type.
4. **Full suite green with zero new failures**, and `vocabulary_fingerprint` unchanged.
