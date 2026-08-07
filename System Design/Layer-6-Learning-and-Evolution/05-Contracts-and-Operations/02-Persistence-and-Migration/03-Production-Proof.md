# Production proof

Schema/text/fake tests prove intended queries and constraints locally. Deployment still must apply
0045 and test the weekly unique claim, `FOR UPDATE` paths, version supersession and TTL expiry
under real PostgreSQL concurrency.
