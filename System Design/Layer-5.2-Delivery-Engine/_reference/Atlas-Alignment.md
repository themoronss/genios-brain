# Atlas alignment · Layer 5.2

| Atlas hierarchy | Documentation location | Runtime mapping |
|---|---|---|
| Part A · Delivery Orchestrator | `01-Delivery-Orchestrator/` | gate, presence, destination, timing, policy, outbox |
| Part B · 11 Delivery Units | `02-Delivery-Units/` | adapters and pull/agent surfaces, with explicit gaps |
| Part C · Delivery Management | `03-Delivery-Management/` | outbox, results and analytics |
| DeliveryObject / DeliveryResult | `04-Contracts-and-Operations/01-Delivery-Contracts/` | `contracts/delivery.py` |
| Card/user scenarios | `_reference/` | card pipeline/actions/slots/digest |
| Storage/API/tests | `04-Contracts-and-Operations/` | migrations 0042/0044 and focused tests |

The Atlas sample tree says `delivery/`; the repository's established package is `deliver/`.
Documentation follows the Layer 5.2 product identity while pointing to the real package. The
package's integer value 6 is only its internal import rank; it is not renamed as a product layer.
