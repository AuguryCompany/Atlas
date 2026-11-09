"""AUGURY CONNECT: adapters for external geospatial data sources.

Connectors never invent data. When offline mode is on, a key is missing or the
upstream fails, they return an empty result (or the real historical catalogue,
for earthquakes) and say so in the ``source`` field, so the UI always shows the
provenance of what is on screen.
"""
