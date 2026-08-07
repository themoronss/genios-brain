# Lifecycle, edge cases and gaps

Application validation requires public HTTPS and rejects obvious localhost/private/link-local
SSRF destinations. Real deployments still need network-level egress controls, DNS/rebinding
defense, secret rotation and receiver-side signature/idempotency verification.

2xx is transport acceptance, not execution. 408/425/429/5xx and network failures are classified
for bounded retry; ambiguous outcomes stay on the same channel. A generic webhook is not silently
treated as an agent route or native email/mobile provider. External reachability and outage
behavior remain provider/deployment proof.
