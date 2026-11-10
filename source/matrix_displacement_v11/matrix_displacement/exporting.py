"""V0.6 CSV result tables; UTF-8 with BOM for Windows Excel interoperability.

Only the Python standard library is used for writing; numerical input comes
from the already-solved model and result. CSV values stay in SI units.
"""
import csv
from pathlib import Path

from .core import Beam2D, Truss2D, _finite_array
from .postprocessing import BeamResponse2D, MemberResponse2D, TrussResponse2D


def _save_table(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def export_results_csv(model, result, directory, *, points=201, include_sections=True):
    """Export node DOFs, end forces, section samples and deformation samples.

    Returns: dict with absolute or relative Paths for created CSV files.
    A teaching trace is NOT required; both solver modes are supported.
    Section forces/deformation follow the member local i->j axis, with
    length m, force N, moment N*m and rotation rad.
    """
    if type(points) is not int or points < 2:
        raise ValueError('points must be an integer >= 2')
    if type(include_sections) is not bool:
        raise ValueError('include_sections must be boolean')
    if set(model.elements) != set(result.element_end_forces_local):
        raise ValueError('Model and analysis results have incompatible elements')
    directory = Path(directory)
    dm = result.dof_manager
    node_rows = []
    for (node, dof), idx in sorted(dm.mapping.items(), key=lambda pair: pair[1]):
        _finite_array(result.displacements[idx:idx+1], 'Displacement')
        _finite_array(result.reactions[idx:idx+1], 'Reaction')
        status = ('inactive' if idx in dm.inactive else
                  'prescribed' if (node, dof) in model.constraints else 'free')
        node_rows.append((idx, node, dof, status,
                          'rad' if dof == 'rz' else 'm',
                          float(result.displacements[idx]),
                          'N*m' if dof == 'rz' else 'N',
                          float(result.reactions[idx])))
    paths = {}
    paths['nodal'] = _save_table(directory/'nodal_results.csv',
                                ('global_dof','node_id','dof','status','displacement_unit',
                                 'displacement','reaction_unit','reaction'), node_rows)
    end_rows = []
    for eid, element in sorted(model.elements.items()):
        q = result.element_end_forces_local[eid]
        _finite_array(q, f'Element {eid} end forces')
        if isinstance(element, Beam2D):
            labels = ('Fy_i','M_i','Fy_j','M_j')
        elif isinstance(element, Truss2D):
            labels = ('Fx_i','Fy_i','Fx_j','Fy_j')
        else:
            labels = ('Fx_i','Fy_i','M_i','Fx_j','Fy_j','M_j')
        for label, value in zip(labels, q):
            end_rows.append((eid, type(element).__name__, label,
                             'N*m' if label.startswith('M') else 'N', float(value)))
    paths['end_forces'] = _save_table(directory/'element_end_forces.csv',
                                     ('element_id','element_type','component','unit','value'), end_rows)
    if not include_sections:
        return paths
    section_rows, deformation_rows = [], []
    for eid, element in sorted(model.elements.items()):
        if isinstance(element, Truss2D):
            response = TrussResponse2D(model,result,eid)
        elif isinstance(element, Beam2D):
            response = BeamResponse2D(model,result,eid)
        else:
            response = MemberResponse2D(model,result,eid)
        sections = response.sample_sections(points)
        d = response.sample_deformation(points)
        for i, x in enumerate(sections.x):
            side = ('left' if i+1 < len(sections.x) and
                    sections.x[i+1] == x else
                    'right' if i and sections.x[i-1] == x else 'regular')
            section_rows.append((eid, type(element).__name__,float(x),side,
                                 float(sections.N[i]),float(sections.V[i]),float(sections.M[i])))
        for i, x in enumerate(d.x):
            deformation_rows.append((eid,type(element).__name__,float(x),
                                     float(d.ux_local[i]),float(d.uy_local[i]),float(d.rz[i]),
                                     float(d.ux_global[i]),float(d.uy_global[i])))
    paths['sections'] = _save_table(directory/'section_forces.csv',
                                    ('element_id','element_type','x_m','side',
                                     'N_N','V_N','M_Nm'),section_rows)
    paths['deformations'] = _save_table(directory/'deformations.csv',
                                        ('element_id','element_type','x_m',
                                         'ux_local_m','uy_local_m','rz_rad',
                                         'ux_global_m','uy_global_m'), deformation_rows)
    return paths
