"""Application layer — use cases + ports.

Use cases orchestrate the aggregate and the infrastructure ports
(repositories, outbox, schema validator). They do NOT touch any specific
driver — every external call is mediated by a port (ABC).
"""
