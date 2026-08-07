# Production proof still required

Repository tests exercise schema text, fakes and behavior. Deployment must still apply migration
0041 to live PostgreSQL and prove indexes/constraints under concurrent sweeps.

The documentation therefore calls the persistence shape built but the production environment
proof partial.
