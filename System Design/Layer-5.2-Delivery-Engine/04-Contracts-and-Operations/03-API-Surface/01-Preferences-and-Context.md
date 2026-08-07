# Preferences and context

Endpoints read/write/delete delivery preferences, resolve effective field-by-field configuration,
list held work, and create/read/delete bounded presence context.

Writes validate timezone and policy values inside the transaction so a saved value cannot silently
degrade at runtime.
