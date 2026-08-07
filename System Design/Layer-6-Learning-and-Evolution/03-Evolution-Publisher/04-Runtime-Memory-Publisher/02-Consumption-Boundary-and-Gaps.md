# Consumption boundary and gaps

PostgreSQL is the source of truth. No Context/Reasoning reader consumes these memories yet, and no
optional Redis acceleration/fallback has been added.

A future reader must query by tenant and viewer, enforce `expires_at` at read time even before the
physical sweep, and treat cache failure as a PostgreSQL fallback rather than extending the lease.
