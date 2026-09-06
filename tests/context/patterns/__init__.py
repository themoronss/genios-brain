"""Package marker: `test_authority.py` exists here AND at tests/capture/validate/, and
pytest's prepend import mode keys a test module on its basename up to the first directory
without an `__init__.py`. Without this file the two collide and collection aborts the whole run.
"""
