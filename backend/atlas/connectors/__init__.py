"""AUGURY CONNECT: adapters for external geospatial data sources.

Every connector degrades gracefully: when offline mode is on, a key is missing,
or the upstream fails, it returns bundled reference data and says so in the
``source`` field, so the UI can label the provenance of what is on screen.
"""
