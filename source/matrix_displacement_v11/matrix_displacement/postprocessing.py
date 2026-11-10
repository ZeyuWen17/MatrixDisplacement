"""V0.6: exact local section-force and elastic-line recovery for Frame2D.

Scope: prismatic Euler--Bernoulli frames with the V0.2 load types
(constant local/global member forces and concentrated member forces).
The member end resisting vector is the vector returned by the V0.2 solver:
[Fx_i, Fy_i, M_i, Fx_j, Fy_j, M_j] in the LOCAL coordinate system.

Diagram conventions (local x directed i->j, local y +90 degrees):
    N(x) = -Fx_i - integral_0^x qx(s) ds - sum(Fx at or before x)
    V(x) = +Fy_i + integral_0^x qy(s) ds + sum(Fy at or before x)
    M(x) = -M_i + integral_0^x V(s) ds
Positive N is tension, positive M is sagging for a horizontal i->j beam.
A point load causes a discontinuity in N or V; use side='left'/'right'.

The displacement fields integrate the exact Euler--Bernoulli equilibrium
relations u'(x)=N(x)/EA, v''(x)=M(x)/EI, rather than interpolating only
nodal degrees of freedom. This captures fixed-fixed beam curvature under
member loads even when all nodal displacements and rotations are zero.
"""
from dataclasses import dataclass
import numpy as np

from .core import Frame2D, Truss2D, Beam2D, PointLoad2D, UniformLoad2D, LinearLoad2D, _finite_float, _finite_array


@dataclass(frozen=True)
class SectionForces2D:
    """Internal forces at local distance x (N, N, N*m)."""
    x: float
    N: float
    V: float
    M: float


@dataclass(frozen=True)
class Deformation2D:
    """Displacements and cross-section rotation at local distance x (m, rad)."""
    x: float
    ux_local: float
    uy_local: float
    rz: float
    ux_global: float
    uy_global: float


@dataclass(frozen=True)
class SectionDiagramSamples:
    """Ordered diagram points; duplicate x at jumps are the left/right limits."""
    x: np.ndarray
    N: np.ndarray
    V: np.ndarray
    M: np.ndarray


@dataclass(frozen=True)
class DeformationSamples:
    """Ordered displacement samples (undeformed x is local member distance)."""
    x: np.ndarray
    ux_local: np.ndarray
    uy_local: np.ndarray
    rz: np.ndarray
    ux_global: np.ndarray
    uy_global: np.ndarray


class MemberResponse2D:
    """Postprocess one solved member without modifying the structural model.

    Args:
        model: StructuralModel used for the solve (must not change afterward).
        result: corresponding AnalysisResult.
        element_id: element to query.
    """

    def __init__(self, model, result, element_id):
        if element_id not in model.elements:
            raise KeyError(f'Unknown element {element_id}')
        if element_id not in result.element_end_forces_local:
            raise ValueError(f'No solved end forces for element {element_id}')
        self.model, self.result, self.element_id = model, result, element_id
        self.element = model.elements[element_id]
        if not isinstance(self.element, (Frame2D, Beam2D)):
            raise TypeError('MemberResponse2D is for bending members; use TrussResponse2D for truss members')
        self.L, self.c, self.s = self.element.geometry(model)
        q_raw = np.asarray(result.element_end_forces_local[element_id], dtype=float)
        if isinstance(self.element, Beam2D):
            if q_raw.shape != (4,):
                raise ValueError('Expected a 4-component Beam2D end-force vector')
            self.q_end = np.array([0.,q_raw[0],q_raw[1],0.,q_raw[2],q_raw[3]])
        else:
            if q_raw.shape != (6,):
                raise ValueError('Expected a 6-component Frame2D end-force vector')
            self.q_end = q_raw
        self.EA = model.materials[self.element.material_id].E * model.sections[self.element.section_id].A
        self.EI = model.materials[self.element.material_id].E * model.sections[self.element.section_id].I
        idx = result.dof_manager.element_indices(self.element)
        nodal_local = self.element.transformation_matrix(model) @ result.displacements[idx]
        if isinstance(self.element, Beam2D):
            self.d_local = np.array([0.,nodal_local[0],nodal_local[1],
                                     0.,nodal_local[2],nodal_local[3]])
        else:
            self.d_local = self.element.physical_local_displacements(model, nodal_local, model.member_loads)
        _finite_array(self.q_end, 'Member end force')
        _finite_array(self.d_local, 'Member local displacement')
        if not np.isfinite(self.EA) or not np.isfinite(self.EI) or self.EA <= 0 or self.EI <= 0:
            raise ValueError('Invalid EA/EI for postprocessing')

        self.qx = 0.0  # value of qx at local x=0
        self.qy = 0.0  # value of qy at local x=0
        self.dqx = 0.0  # end-minus-start qx, divided by L in use
        self.dqy = 0.0
        self.point_loads = []  # (position, local Fx, local Fy)
        for load in model.member_loads:
            if load.element_id != element_id:
                continue
            if isinstance(load, UniformLoad2D):
                qx, qy = self.element._load_vector_in_local_axes(model, load.qx, load.qy, load.system)
                self.qx += qx
                self.qy += qy
            elif isinstance(load, LinearLoad2D):
                qxi, qyi = self.element._load_vector_in_local_axes(
                    model, load.qx_i, load.qy_i, load.system)
                qxj, qyj = self.element._load_vector_in_local_axes(
                    model, load.qx_j, load.qy_j, load.system)
                self.qx += qxi
                self.qy += qyi
                self.dqx += qxj-qxi
                self.dqy += qyj-qyi
            elif isinstance(load, PointLoad2D):
                # Revalidate for callers that mutated a public list after the solve.
                self.element.equivalent_nodal_load(model, load)
                fx, fy = self.element._load_vector_in_local_axes(model, load.fx, load.fy, load.system)
                self.point_loads.append((load.position, fx, fy))
            else:
                raise TypeError('Unsupported member load type')
        _finite_array(np.array([self.qx, self.qy, self.dqx, self.dqy]), 'Accumulated member line load')

    def _x(self, x):
        x = _finite_float(x, 'Section x')
        if not 0.0 <= x <= self.L:
            raise ValueError(f'Section x must lie within [0, {self.L}] m')
        return x

    def section(self, x, side='right'):
        """N, V, M at x. For point loads, side controls which limit is returned.

        At a force location, 'left' excludes that point force; 'right' includes it.
        End-point concentrated forces should be queried with x=0, side='right'
        and x=L, side='left' for *interior* element diagrams.
        """
        x = self._x(x)
        if side not in ('left', 'right'):
            raise ValueError("side must be 'left' or 'right'")
        Fxi, Fyi, Mi = self.q_end[:3]
        N = -Fxi - self.qx*x - self.dqx*x*x/(2*self.L)
        V = Fyi + self.qy*x + self.dqy*x*x/(2*self.L)
        M = -Mi + Fyi*x + self.qy*x*x/2 + self.dqy*x**3/(6*self.L)
        tol = 1e-12 * max(1.0, self.L)
        for a, fx, fy in self.point_loads:
            if x > a + tol or (side == 'right' and x >= a - tol):
                N -= fx
                V += fy
            # The point force makes no jump in bending moment.
            if x > a:
                M += fy * (x-a)
        _finite_array(np.array([N, V, M]), 'Section forces')
        return SectionForces2D(x, float(N), float(V), float(M))

    def deformation(self, x):
        """u(x), v(x), theta(x), with all member loads included exactly.

        Curvature is v''(x)=M(x)/EI; u'(x)=N(x)/EA. Uses small-rotation
        linear beam theory and interpolates smoothly across point forces.
        """
        x = self._x(x)
        Fxi, Fyi, Mi = self.q_end[:3]
        ui, vi, theta_i = self.d_local[:3]
        axial_int = -Fxi*x - self.qx*x*x/2 - self.dqx*x**3/(6*self.L)
        bend_int = (-Mi*x*x/2 + Fyi*x**3/6 + self.qy*x**4/24
                    + self.dqy*x**5/(120*self.L))
        rotation_int = (-Mi*x + Fyi*x*x/2 + self.qy*x**3/6
                        + self.dqy*x**4/(24*self.L))
        for a, fx, fy in self.point_loads:
            z = max(0.0, x-a)
            axial_int -= fx*z
            bend_int += fy*z**3/6
            rotation_int += fy*z*z/2
        u = ui + axial_int / self.EA
        v = vi + theta_i*x + bend_int / self.EI
        theta = theta_i + rotation_int / self.EI
        gx = self.c*u - self.s*v
        gy = self.s*u + self.c*v
        _finite_array(np.array([u, v, theta, gx, gy]), 'Member deformation')
        return Deformation2D(x, float(u), float(v), float(theta), float(gx), float(gy))

    def _critical_positions(self):
        """Exact moment-extremum candidates V(x)=0 between point loads.

        With a linear distributed load, V(x) is quadratic on each interval.
        The root test rejects complex/out-of-interval candidates.
        """
        positions = [0.0] + sorted({a for a, _, _ in self.point_loads if 0 < a < self.L}) + [self.L]
        roots = []
        for a, b in zip(positions[:-1], positions[1:]):
            mid = (a+b)/2
            base = self.section(mid).V - self.qy*mid - self.dqy*mid*mid/(2*self.L)
            # Solve in dimensionless t=x/L so coefficient magnitudes are comparable.
            coefficients = [self.dqy*self.L/2, self.qy*self.L, base]
            if abs(coefficients[0]) <= 1e-14 * max(abs(z) for z in coefficients):
                if coefficients[1] == 0:
                    continue
                candidates = [-coefficients[2]/coefficients[1]]
            else:
                candidates = np.roots(coefficients)
            for root in candidates:
                if abs(np.imag(root)) < 1e-10:
                    xr = float(np.real(root)) * self.L
                    if a < xr < b and all(abs(xr-r) > 1e-10*self.L for r in roots):
                        roots.append(xr)
        return sorted(roots)

    def sample_sections(self, points=201):
        """Sample N,V,M; preserve jumps and exact moment stationary positions."""
        if not isinstance(points, int) or isinstance(points, bool) or points < 2:
            raise ValueError('points must be an integer >= 2')
        breaks = [a for a, _, _ in self.point_loads if 0 < a < self.L]
        x_positions = sorted(set(np.linspace(0, self.L, points).tolist() + breaks + self._critical_positions()))
        xs, ns, vs, ms = [], [], [], []
        tol = 1e-12*max(1.0, self.L)
        for x in x_positions:
            is_jump = any(abs(x-a) <= tol for a in breaks)
            sides = ('left','right') if is_jump else (('left',) if x == self.L else ('right',))
            for side in sides:
                forces = self.section(x, side)
                xs.append(x); ns.append(forces.N); vs.append(forces.V); ms.append(forces.M)
        return SectionDiagramSamples(*(np.array(values, dtype=float) for values in (xs,ns,vs,ms)))

    def sample_deformation(self, points=201):
        if not isinstance(points, int) or isinstance(points, bool) or points < 2:
            raise ValueError('points must be an integer >= 2')
        values = [self.deformation(float(x)) for x in np.linspace(0,self.L,points)]
        return DeformationSamples(*(
            np.array([getattr(value, key) for value in values], dtype=float)
            for key in ('x','ux_local','uy_local','rz','ux_global','uy_global')
        ))


class BeamResponse2D(MemberResponse2D):
    """Postprocessing for horizontal continuous-beam elements (bending only)."""

    def __init__(self, model, result, element_id):
        if element_id not in model.elements or not isinstance(model.elements[element_id], Beam2D):
            raise TypeError('BeamResponse2D requires a Beam2D element')
        super().__init__(model, result, element_id)


class TrussResponse2D:
    """Axial section force and linearly interpolated truss deformations.

    V=M=0 for the ideal pin-ended axial-only Truss2D. No member loads in V0.4.
    """

    def __init__(self, model, result, element_id):
        if element_id not in model.elements or not isinstance(model.elements[element_id], Truss2D):
            raise TypeError('TrussResponse2D requires a Truss2D element')
        self.element = model.elements[element_id]
        self.model, self.result, self.element_id = model,result,element_id
        self.L,self.c,self.s = self.element.geometry(model)
        self.q_end = result.element_end_forces_local[element_id]
        idx = result.dof_manager.element_indices(self.element)
        self.d_local = self.element.transformation_matrix(model) @ result.displacements[idx]
        self.N = float(-self.q_end[0])
        self.EA = model.materials[self.element.material_id].E * model.sections[self.element.section_id].A

    def _x(self, x):
        x = _finite_float(x, 'Section x')
        if not 0 <= x <= self.L:
            raise ValueError(f'Section x must lie within [0, {self.L}] m')
        return x

    def section(self, x, side='right'):
        x = self._x(x)
        if side not in ('left','right'):
            raise ValueError("side must be 'left' or 'right'")
        return SectionForces2D(x, self.N, 0.0, 0.0)

    def deformation(self, x):
        x = self._x(x)
        t = x/self.L
        di,dj = self.d_local[:2], self.d_local[2:]
        uv = di*(1-t) + dj*t
        u,v = uv
        gx,gy = self.c*u - self.s*v, self.s*u + self.c*v
        return Deformation2D(x,float(u),float(v),0.,float(gx),float(gy))

    def sample_sections(self, points=201):
        if not isinstance(points,int) or isinstance(points,bool) or points < 2:
            raise ValueError('points must be an integer >= 2')
        x = np.linspace(0,self.L,points)
        return SectionDiagramSamples(x,np.full_like(x,self.N),np.zeros_like(x),np.zeros_like(x))

    def sample_deformation(self, points=201):
        if not isinstance(points,int) or isinstance(points,bool) or points < 2:
            raise ValueError('points must be an integer >= 2')
        values = [self.deformation(float(x)) for x in np.linspace(0,self.L,points)]
        return DeformationSamples(*(
            np.array([getattr(value, key) for value in values], dtype=float)
            for key in ('x','ux_local','uy_local','rz','ux_global','uy_global')
        ))
