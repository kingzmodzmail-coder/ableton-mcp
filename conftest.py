# Ensures `import MCP_Server.server` resolves no matter how pytest is invoked.
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The contracts package is intentionally kept under ``packages/`` in the
# monorepo.  Keep source-tree test runs equivalent to an installed package.
_contracts_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packages", "contracts")
if _contracts_root not in sys.path:
    sys.path.insert(0, _contracts_root)
