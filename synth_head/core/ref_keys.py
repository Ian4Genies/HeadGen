"""
String constants for pipeline object reference keys.

Each constant corresponds to a PointerProperty declared on
SYNTHHEAD_PG_PipelineRefs in operators.py.  Import these instead of
using bare strings so typos are caught at import time.
"""

MESH: str = "mesh"
BODY_GEO: str = "body_geo"
ARMATURE: str = "armature"
HEAD_MAT: str = "head_mat"
L_EYE: str = "L_eye"
R_EYE: str = "R_eye"
EYEBROWS: str = "eyebrows"
EYELASHES: str = "eyelashes"
EYE_MAT: str = "eye_mat"