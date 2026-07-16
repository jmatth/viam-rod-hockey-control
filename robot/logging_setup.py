"""Logging setup for the CLI entry points.

Library modules just do `log = logging.getLogger(__name__)` and log; only the
entry points below decide where those records go.
"""

import logging

# Source location first, so the eye lands on it when scanning a column of lines.
LOG_FORMAT = "%(filename)s:%(lineno)d  %(message)s"


def configure(level=logging.INFO, quiet_viam=False):
    """Route this project's logs to stdout, without doubling up the Viam SDK's.

    The SDK attaches its own stdout/stderr handlers to every `viam.*` logger, so
    with propagation left on, each SDK record would print once from the SDK's
    handler and again from the root handler basicConfig installs.

    quiet_viam drops the SDK's routine INFO connection chatter for tools that
    want a clean report. It goes through viam.logging.setLevel because the SDK
    re-applies its own level to each logger when it re-adds handlers at connect
    time, which would undo a plain setLevel on those loggers.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger("viam").propagate = False
    if quiet_viam:
        # Imported lazily so the SDK-free entry points (simulate.py) don't pay for it.
        import viam.logging
        viam.logging.setLevel(logging.WARNING)
