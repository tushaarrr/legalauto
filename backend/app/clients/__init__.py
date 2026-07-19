"""External enrichment clients.

One module per source, each independently testable and each returning a
SourceResult rather than raising. See base.py for the shared retry, cache, and
robots.txt machinery.
"""
