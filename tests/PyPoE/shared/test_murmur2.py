"""


Overview
-------------------------------------------------------------------------------

+----------+------------------------------------------------------------------+
| Path     | tests/PyPoE/shared/test_murmur2.py                               |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                                                             |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
-------------------------------------------------------------------------------



Agreement
-------------------------------------------------------------------------------

See PyPoE/LICENSE
"""

# =============================================================================
# Imports
# =============================================================================

# Python

# 3rd-party
import pytest

# self
from PyPoE.shared import murmur2

# =============================================================================
# Setup
# =============================================================================

data = [
    ('This is a test'.encode('ascii'), 895688205, 0),
    ('This is a test'.encode('ascii'), 1204582478, 42),
]

# =============================================================================
# Fixtures
# =============================================================================

# =============================================================================
# Tests
# =============================================================================

@pytest.mark.parametrize('data,result,seed', data)
def test_murmur2_32(data, result, seed):
    assert murmur2.murmur2_32(data, seed) == result