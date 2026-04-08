"""
String constants for pipeline object reference keys.

Each constant corresponds to a PointerProperty declared on
SYNTHHEAD_PG_PipelineRefs in operators.py.  Import these instead of
using bare strings so typos are caught at import time.
"""

MESH: str = "mesh"
ARMATURE: str = "armature"
HEAD_MAT: str = "head_mat"
