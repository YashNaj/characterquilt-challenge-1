# cq-screen

    python3 -m venv .venv && .venv/bin/pip install pytest requests
    .venv/bin/python -m pytest
    CQ_START_CLOCK=1 .venv/bin/python -m cq.cli probe GET /s1   # starts the clock
    .venv/bin/python -m cq.cli status
    .venv/bin/python -m cq.cli report            # dry run
    .venv/bin/python -m cq.cli report --post --yes

Key is read from `CQ_KEY` or `key.txt` (git-ignored).
