# Version and supersession

The publisher locks the active tenant+brain+subject row, increments its version, deactivates it
with ended reason `superseded`, transitions the old LearningObject, then inserts the new active entry.

One active version is a database rule, not a client convention.
