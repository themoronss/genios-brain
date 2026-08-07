from __future__ import annotations

# Knowledge could be WRITTEN but never listed or deleted (uploads had both). These add a GET list
# and a DELETE. The endpoints need a DB at runtime, but this at least locks in that the routes are
# registered and the module imports cleanly (it uses no Form/File, so it imports without multipart).


def test_knowledge_list_and_delete_routes_registered():
    from genios_engine.api import knowledge_routes

    pairs = {(r.path, m) for r in knowledge_routes.router.routes
             for m in getattr(r, "methods", set())}
    assert ("/api/org/{org_id}/knowledge", "GET") in pairs          # list (new)
    assert ("/api/org/{org_id}/knowledge/{key}", "DELETE") in pairs  # delete (new)
    assert ("/api/org/{org_id}/knowledge", "POST") in pairs         # write (unchanged)
    assert ("/api/org/{org_id}/knowledge/kinds", "GET") in pairs    # vocabulary (unchanged)
