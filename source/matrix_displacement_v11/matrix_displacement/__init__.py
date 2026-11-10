"""Educational matrix-displacement 2D frame solver, V1.1."""
from .core import (
    Node, Material, Section, Frame2D, Truss2D, Beam2D, UniformLoad2D, LinearLoad2D, PointLoad2D,
    StructuralModel, DOFManager, LinearStaticSolver, AnalysisResult, Mode,
)
from .postprocessing import (
    MemberResponse2D, TrussResponse2D, BeamResponse2D, SectionForces2D, Deformation2D,
    SectionDiagramSamples, DeformationSamples,
)
from .visualization import (
    plot_structure, plot_force_diagram, plot_deformed_shape,
    plot_member_section_diagram,
)

__version__ = '1.1.6'

from .io import model_to_dict, model_from_dict, save_model_json, load_model_json
from .reporting import render_teaching_report, save_teaching_report

from .exporting import export_results_csv

from .editor import ModelEditor

from .history import EditHistory
from .inspection import inspect_node, inspect_member, NodeInspection, MemberInspection

from .interaction import dimension_info, project_to_member, diagram_pick, DimensionInfo, ProjectedStation, DiagramPick
from .diagnostics import explain_error, ErrorExplanation

from .recovery import RecoveryStore, RecoveryEntry, default_recovery_directory
