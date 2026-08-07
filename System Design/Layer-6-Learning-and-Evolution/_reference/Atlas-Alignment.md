# Atlas alignment · Layer 6 Learning & Evolution

| Atlas hierarchy | Documentation location | Runtime mapping |
|---|---|---|
| Part A · Learning Orchestrator | `01-Learning-Orchestrator/` | orchestrator, store, governance |
| Part B · 11 Learning Units | `02-Learning-Units/` | `feedback/units.py` + Unit 11 in governance |
| Part C · Evolution Publisher | `03-Evolution-Publisher/` | `feedback/store.py::publish` |
| Promotion lifecycle | `04-Promotion-Lifecycle/` | contract states/path + guarded store transitions |
| LearningObject | `05-Contracts-and-Operations/01-LearningObject-Contract/` | `contracts/learning.py` |
| Storage/API/tests | `05-Contracts-and-Operations/` | migration 0045, learning routes/tests |

The Atlas and product architecture call this Layer 6. The package's internal import rank is 7;
that rank is not a product layer. No Expert publisher exists.
The Atlas's three dynamic brains are publication targets, not permission for silent runtime
mutation; consumer seams remain explicitly partial.
