"""V0.6 two-dimensional linear static frame, truss, and continuous beam analysis (SI units).

Frame rotational end releases are statically condensed before assembly.
A released end rotation has no connection to the global nodal rotation.
"""
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

DOFS = ('ux', 'uy', 'rz')

# A numerical diagnostic (not a universal proof of structural stability).
MIN_NORMALIZED_EIGENVALUE = 1e-12


def _finite_float(value, name):
    """Convert a value to a finite float or raise an actionable error."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite real number') from exc
    if not np.isfinite(number):
        raise ValueError(f'{name} must be a finite real number')
    return number


def _finite_array(array, name):
    if not np.all(np.isfinite(array)):
        raise ValueError(f'{name} contains a non-finite result: check data and units')
    return array


class StabilityError(ValueError):
    """Numerical instability with inspectable node/DOF locations."""
    def __init__(self, message, dofs=(), *, suspected=False):
        super().__init__(message)
        self.dofs = tuple(dofs)
        self.node_ids = tuple(sorted({node for node, _ in self.dofs}))
        self.suspected = suspected


def _check_reduced_stiffness(Kff, dof_keys=()):
    """Check typical mechanisms and extreme numerical near-singularity."""
    if Kff.size == 0:
        return
    _finite_array(Kff, 'Stiffness matrix')
    diag = np.diag(Kff)
    if np.any(diag <= 0):
        locations = [dof_keys[i] for i in np.flatnonzero(diag <= 0)] if dof_keys else []
        raise StabilityError('Singular stiffness matrix: non-positive diagonal; check constraints and disconnected nodes', locations)
    scale = np.sqrt(diag)
    normalized = (Kff / scale[:, None]) / scale[None, :]
    normalized = 0.5 * (normalized + normalized.T)
    eigenvalues = np.linalg.eigvalsh(normalized)
    if not np.all(np.isfinite(eigenvalues)) or eigenvalues[0] <= MIN_NORMALIZED_EIGENVALUE:
        locations = []
        if dof_keys and np.all(np.isfinite(eigenvalues)):
            # Inspect the normalized near-null mode only after stability failed.
            # These are investigation candidates, not a unique physical cause.
            _, vectors = np.linalg.eigh(normalized)
            weights = np.abs(vectors[:, 0])
            indices = np.argsort(-weights)
            locations = [dof_keys[i] for i in indices[:8] if weights[i] >= .2 * weights.max()]
        raise StabilityError(
            'Singular or near-singular stiffness matrix: check supports, mechanisms, '
            'disconnected nodes, and extreme stiffness ratios', locations, suspected=True
        )


class Mode(str, Enum):
    TEACHING = 'teaching'
    FAST = 'fast'


@dataclass(frozen=True)
class Node:
    id: int
    x: float
    y: float

    def __post_init__(self):
        object.__setattr__(self, 'x', _finite_float(self.x, 'Node x'))
        object.__setattr__(self, 'y', _finite_float(self.y, 'Node y'))


@dataclass(frozen=True)
class Material:
    id: int
    E: float

    def __post_init__(self):
        E = _finite_float(self.E, 'E')
        if E <= 0:
            raise ValueError('E must be positive')
        object.__setattr__(self, 'E', E)


@dataclass(frozen=True)
class Section:
    id: int
    A: float
    I: float

    def __post_init__(self):
        A = _finite_float(self.A, 'A')
        I = _finite_float(self.I, 'I')
        if A <= 0 or I <= 0:
            raise ValueError('A and I must be positive')
        object.__setattr__(self, 'A', A)
        object.__setattr__(self, 'I', I)


@dataclass(frozen=True)
class UniformLoad2D:
    """Constant line load (qx,qy in N/m) on one complete element.

    system='local': x follows node_i -> node_j; local y is +90 deg from x.
    system='global': qx/qy refer to the global X/Y axes.
    """
    element_id: int
    qx: float = 0.0
    qy: float = 0.0
    system: str = 'local'

    def __post_init__(self):
        object.__setattr__(self, 'qx', _finite_float(self.qx, 'Uniform qx'))
        object.__setattr__(self, 'qy', _finite_float(self.qy, 'Uniform qy'))
        if self.system not in ('local', 'global'):
            raise ValueError("Load coordinate system must be 'local' or 'global'")


@dataclass(frozen=True)
class LinearLoad2D:
    """Linearly varying full-length force [N/m] from end i to end j.

    q_i and q_j are vector components in the chosen coordinate system.
    Example: triangular downward load qy_i=0, qy_j=-1000.
    """
    element_id: int
    qx_i: float = 0.0
    qy_i: float = 0.0
    qx_j: float = 0.0
    qy_j: float = 0.0
    system: str = 'local'

    def __post_init__(self):
        for name in ('qx_i', 'qy_i', 'qx_j', 'qy_j'):
            object.__setattr__(self, name, _finite_float(getattr(self, name), f'Linear {name}'))
        if self.system not in ('local', 'global'):
            raise ValueError("Load coordinate system must be 'local' or 'global'")


@dataclass(frozen=True)
class PointLoad2D:
    """Concentrated force (fx,fy in N) at a metres from element node_i.

    Applies a FORCE (no separate applied concentrated couple in V0.2).
    Position a is measured along the undeformed local x-axis.
    """
    element_id: int
    position: float
    fx: float = 0.0
    fy: float = 0.0
    system: str = 'local'

    def __post_init__(self):
        object.__setattr__(self, 'position', _finite_float(self.position, 'Point load position'))
        object.__setattr__(self, 'fx', _finite_float(self.fx, 'Point fx'))
        object.__setattr__(self, 'fy', _finite_float(self.fy, 'Point fy'))
        if self.system not in ('local', 'global'):
            raise ValueError("Load coordinate system must be 'local' or 'global'")


@dataclass(frozen=True)
class Frame2D:
    id: int
    node_i: int
    node_j: int
    material_id: int
    section_id: int
    release_i: bool = False
    release_j: bool = False

    @property
    def local_dofs(self):
        return ('ux', 'uy', 'rz', 'ux', 'uy', 'rz')

    @property
    def released_indices(self):
        return tuple(i for i, flag in ((2,self.release_i),(5,self.release_j)) if flag)

    def _condense(self, model, f_original=None):
        """Return effective (k,f) with released rotations statically eliminated.

        For partition (a=retained,r=released):
          k_eff_aa = k_aa - k_ar @ inv(k_rr) @ k_ra
          f_eff_a = f_a - k_ar @ inv(k_rr) @ f_r
        Released rows/columns and equivalent nodal moments are zero.
        """
        k = self._raw_local_stiffness(model)
        f = np.zeros(6) if f_original is None else np.asarray(f_original, dtype=float)
        released = self.released_indices
        if not released:
            return k, f.copy()
        r = np.array(released, dtype=int)
        a = np.array([i for i in range(6) if i not in released], dtype=int)
        kar = k[np.ix_(a,r)]
        kra = k[np.ix_(r,a)]
        krr = k[np.ix_(r,r)]
        # Eliminate internal hinge rotations, never the unreleased nodal DOFs.
        k_eff = np.zeros((6,6))
        f_eff = np.zeros(6)
        k_eff[np.ix_(a,a)] = k[np.ix_(a,a)] - kar @ np.linalg.solve(krr,kra)
        f_eff[a] = f[a] - kar @ np.linalg.solve(krr,f[r])
        k_eff = 0.5*(k_eff+k_eff.T)
        return _finite_array(k_eff, 'Condensed stiffness'), _finite_array(f_eff, 'Condensed load')

    def physical_local_displacements(self, model, nodal_local_displacements, member_loads=()):
        """Recover actual released end rotations from zero-moment equilibrium.

        Nodal rz at a released end is NOT the beam-end cross-section rotation.
        This method reconstructs the released internal rotation from unreleased
        node translations/rotations and the original (uncondensed) member loads.
        """
        d = np.array(nodal_local_displacements, dtype=float, copy=True)
        released = self.released_indices
        if released:
            f = np.zeros(6)
            for load in member_loads:
                if load.element_id == self.id:
                    f += self._original_equivalent_nodal_load(model, load)
            k = self._raw_local_stiffness(model)
            r = np.array(released,dtype=int)
            a = np.array([j for j in range(6) if j not in released],dtype=int)
            d[r] = np.linalg.solve(k[np.ix_(r,r)], f[r] - k[np.ix_(r,a)] @ d[a])
        return _finite_array(d, 'Physical member-end displacements')

    def geometry(self, model):
        a, b = model.nodes[self.node_i], model.nodes[self.node_j]
        dx, dy = b.x-a.x, b.y-a.y
        L = float(np.hypot(dx, dy))
        if L <= 0:
            raise ValueError(f'Element {self.id} has zero length')
        if not np.isfinite(L):
            raise ValueError(f'Element {self.id} has non-finite length: check coordinates')
        return L, dx/L, dy/L

    def _raw_local_stiffness(self, model):
        L, _, _ = self.geometry(model)
        E = model.materials[self.material_id].E
        A, I = model.sections[self.section_id].A, model.sections[self.section_id].I
        a, b, c, d = E*A/L, 12*E*I/L**3, 6*E*I/L**2, 4*E*I/L
        e = 2*E*I/L
        return _finite_array(np.array([
            [a,0,0,-a,0,0],
            [0,b,c,0,-b,c],
            [0,c,d,0,-c,e],
            [-a,0,0,a,0,0],
            [0,-b,-c,0,b,-c],
            [0,c,e,0,-c,d],
        ], dtype=float), f'Element {self.id} stiffness')

    def local_stiffness(self, model):
        """Effective 6x6 matrix; released rotational rows/columns are zero."""
        return self._condense(model)[0]

    def transformation_matrix(self, model):
        _, c, s = self.geometry(model)
        r = np.array([[c,s,0],[-s,c,0],[0,0,1]], dtype=float)
        T = np.zeros((6,6), dtype=float)
        T[:3,:3], T[3:,3:] = r, r
        return T  # local displacement = T @ global displacement

    def global_stiffness(self, model):
        T = self.transformation_matrix(model)
        return T.T @ self.local_stiffness(model) @ T

    def _load_vector_in_local_axes(self, model, x, y, system):
        if system == 'local':
            return x, y
        if system != 'global':
            raise ValueError("Load coordinate system must be 'local' or 'global'")
        _, c, s = self.geometry(model)
        return c*x+s*y, -s*x+c*y

    def _original_equivalent_nodal_load(self, model, load):
        """Unreleased consistent LOCAL load [Fx_i,Fy_i,M_i,Fx_j,Fy_j,M_j].

        +Force and +Moment agree with ux/uy/CCW rz. These vectors are positive
        EXTERNAL equivalent nodal forces; the fixed-end RESISTING force is -f_eq.
        """
        if load.element_id != self.id:
            raise ValueError(f'Load belongs to element {load.element_id}, not {self.id}')
        L, _, _ = self.geometry(model)
        if isinstance(load, UniformLoad2D):
            qx, qy = self._load_vector_in_local_axes(model, load.qx, load.qy, load.system)
            f = np.array([qx*L/2, qy*L/2, qy*L**2/12,
                          qx*L/2, qy*L/2, -qy*L**2/12], dtype=float)
        elif isinstance(load, LinearLoad2D):
            qxi, qyi = self._load_vector_in_local_axes(model, load.qx_i, load.qy_i, load.system)
            qxj, qyj = self._load_vector_in_local_axes(model, load.qx_j, load.qy_j, load.system)
            f = np.array([
                L*(2*qxi+qxj)/6,
                L*(7*qyi+3*qyj)/20,
                L**2*(3*qyi+2*qyj)/60,
                L*(qxi+2*qxj)/6,
                L*(3*qyi+7*qyj)/20,
                -L**2*(2*qyi+3*qyj)/60,
            ], dtype=float)
        elif isinstance(load, PointLoad2D):
            a = _finite_float(load.position, 'Point load position')
            if not 0 <= a <= L:
                raise ValueError(f'Point load position must be in [0, {L}] m for element {self.id}')
            fx, fy = self._load_vector_in_local_axes(model, load.fx, load.fy, load.system)
            t = a / L
            N1 = 1 - 3*t*t + 2*t**3
            N2 = L*(t - 2*t*t + t**3)
            N3 = 3*t*t - 2*t**3
            N4 = L*(-t*t + t**3)
            f = np.array([fx*(1-t), fy*N1, fy*N2,
                          fx*t, fy*N3, fy*N4], dtype=float)
        else:
            raise TypeError('Only UniformLoad2D, LinearLoad2D and PointLoad2D are supported')
        return _finite_array(f, f'Element {self.id} equivalent nodal load')


    def equivalent_nodal_load(self, model, load):
        original = self._original_equivalent_nodal_load(model, load)
        return self._condense(model, original)[1]




@dataclass(frozen=True)
class Beam2D:
    """Horizontal left-to-right Euler--Bernoulli beam (uy,rz at each end).

    This is a bending-only continuous beam; ux is deliberately absent.
    The positive local and global y axes coincide. For sloping beams or beams
    carrying axial force, use Frame2D instead.
    """
    id: int
    node_i: int
    node_j: int
    material_id: int
    section_id: int

    @property
    def local_dofs(self):
        return ('uy', 'rz', 'uy', 'rz')

    def geometry(self, model):
        a, b = model.nodes[self.node_i], model.nodes[self.node_j]
        if b.x <= a.x or b.y != a.y:
            raise ValueError(
                f'Beam2D element {self.id} requires horizontal nodes with x_j > x_i; '
                'use Frame2D for inclined or reversed members'
            )
        L = b.x - a.x
        if not np.isfinite(L):
            raise ValueError(f'Beam2D element {self.id} has non-finite length')
        return L, 1.0, 0.0

    def local_stiffness(self, model):
        L, _, _ = self.geometry(model)
        EI = model.materials[self.material_id].E * model.sections[self.section_id].I
        a, b, c, d = 12*EI/L**3, 6*EI/L**2, 4*EI/L, 2*EI/L
        return _finite_array(np.array([
            [ a, b, -a, b],
            [ b, c, -b, d],
            [-a,-b,  a,-b],
            [ b, d, -b, c],
        ], dtype=float), f'Beam2D element {self.id} stiffness')

    def transformation_matrix(self, model):
        self.geometry(model)
        return np.eye(4)

    def global_stiffness(self, model):
        return self.local_stiffness(model)

    def _load_vector_in_local_axes(self, model, x, y, system):
        # This horizontal positive-x-only element has identical local/global axes.
        if system not in ('local', 'global'):
            raise ValueError("Load coordinate system must be 'local' or 'global'")
        return x, y

    def equivalent_nodal_load(self, model, load):
        if load.element_id != self.id:
            raise ValueError(f'Load belongs to element {load.element_id}, not {self.id}')
        L, _, _ = self.geometry(model)
        if isinstance(load, UniformLoad2D):
            qx, qy = self._load_vector_in_local_axes(model, load.qx, load.qy, load.system)
            if qx != 0:
                raise ValueError('Beam2D carries transverse loads only (qx must be zero)')
            f = [qy*L/2, qy*L**2/12, qy*L/2, -qy*L**2/12]
        elif isinstance(load, LinearLoad2D):
            qxi, qyi = self._load_vector_in_local_axes(model, load.qx_i, load.qy_i, load.system)
            qxj, qyj = self._load_vector_in_local_axes(model, load.qx_j, load.qy_j, load.system)
            if qxi != 0 or qxj != 0:
                raise ValueError('Beam2D carries transverse loads only (qx must be zero)')
            f = [L*(7*qyi+3*qyj)/20, L**2*(3*qyi+2*qyj)/60,
                 L*(3*qyi+7*qyj)/20, -L**2*(2*qyi+3*qyj)/60]
        elif isinstance(load, PointLoad2D):
            if not 0 <= load.position <= L:
                raise ValueError(f'Point load position must be in [0, {L}] m for element {self.id}')
            fx, fy = self._load_vector_in_local_axes(model, load.fx, load.fy, load.system)
            if fx != 0:
                raise ValueError('Beam2D carries transverse loads only (fx must be zero)')
            t = load.position/L
            f = [fy*(1-3*t*t+2*t**3), fy*L*(t-2*t*t+t**3),
                 fy*(3*t*t-2*t**3), fy*L*(-t*t+t**3)]
        else:
            raise TypeError('Only UniformLoad2D, LinearLoad2D and PointLoad2D are supported')
        return _finite_array(np.asarray(f, dtype=float), f'Beam2D element {self.id} equivalent load')


@dataclass(frozen=True)
class Truss2D:
    """Two-node pin-jointed 2D bar with 4 translational element DOFs.

    Sections reuse Section(A,I); I is ignored for truss and retained for
    backward-compatible model storage. Member loads are NOT supported in V0.4;
    apply nodal loads to a subdivided truss instead.
    """
    id: int
    node_i: int
    node_j: int
    material_id: int
    section_id: int

    @property
    def local_dofs(self):
        return ('ux','uy','ux','uy')

    def geometry(self, model):
        a,b = model.nodes[self.node_i],model.nodes[self.node_j]
        dx,dy = b.x-a.x,b.y-a.y
        L = float(np.hypot(dx,dy))
        if L <= 0:
            raise ValueError(f'Element {self.id} has zero length')
        if not np.isfinite(L):
            raise ValueError(f'Element {self.id} has non-finite length')
        return L,dx/L,dy/L

    def local_stiffness(self, model):
        L,_,_ = self.geometry(model)
        EA = model.materials[self.material_id].E * model.sections[self.section_id].A
        k = EA/L
        return _finite_array(np.array([
            [k,0,-k,0],
            [0,0,0,0],
            [-k,0,k,0],
            [0,0,0,0],
        ]), f'Truss {self.id} stiffness')

    def transformation_matrix(self, model):
        _,c,s = self.geometry(model)
        rot = np.array([[c,s],[-s,c]])
        T = np.zeros((4,4))
        T[:2,:2],T[2:,2:] = rot,rot
        return T

    def global_stiffness(self, model):
        T = self.transformation_matrix(model)
        return T.T @ self.local_stiffness(model) @ T

    def equivalent_nodal_load(self, model, load):
        raise ValueError('Truss2D supports nodal loads only in V0.4; subdivide the bar to apply intermediate forces')


@dataclass
class StructuralModel:
    nodes: dict[int,Node] = field(default_factory=dict)
    materials: dict[int,Material] = field(default_factory=dict)
    sections: dict[int,Section] = field(default_factory=dict)
    elements: dict[int,Frame2D | Truss2D | Beam2D] = field(default_factory=dict)
    constraints: dict[tuple[int,str],float] = field(default_factory=dict)
    loads: dict[tuple[int,str],float] = field(default_factory=dict)
    member_loads: list[UniformLoad2D | LinearLoad2D | PointLoad2D] = field(default_factory=list)

    def add_node(self, node):
        if node.id in self.nodes:
            raise ValueError('Duplicate node id')
        self.nodes[node.id] = node

    def add_material(self, material):
        if material.id in self.materials:
            raise ValueError('Duplicate material id')
        self.materials[material.id] = material

    def add_section(self, section):
        if section.id in self.sections:
            raise ValueError('Duplicate section id')
        self.sections[section.id] = section

    def add_element(self, element):
        if element.id in self.elements:
            raise ValueError('Duplicate element id')
        if element.node_i not in self.nodes or element.node_j not in self.nodes:
            raise ValueError('Element references unknown node')
        if element.material_id not in self.materials or element.section_id not in self.sections:
            raise ValueError('Element references unknown material/section')
        element.geometry(self)
        self.elements[element.id] = element

    def _check_dof(self, node_id, dof):
        if node_id not in self.nodes or dof not in DOFS:
            raise ValueError(f'Invalid degree of freedom: {(node_id,dof)}')

    def constrain(self, node_id, dof, value=0.0):
        self._check_dof(node_id,dof)
        self.constraints[(node_id,dof)] = _finite_float(value, 'Prescribed displacement')

    def add_load(self, node_id, dof, value):
        self._check_dof(node_id,dof)
        key = (node_id,dof)
        val = _finite_float(value, 'Nodal load')
        total = self.loads.get(key,0.0) + val
        self.loads[key] = _finite_float(total, 'Accumulated nodal load')

    def add_member_load(self, load):
        if not isinstance(load, (UniformLoad2D, LinearLoad2D, PointLoad2D)):
            raise TypeError('Only UniformLoad2D, LinearLoad2D or PointLoad2D are supported')
        if load.element_id not in self.elements:
            raise ValueError(f'Member load references unknown element {load.element_id}')
        # Validate the geometry, range, and finite equivalent force at input time.
        self.elements[load.element_id].equivalent_nodal_load(self, load)
        self.member_loads.append(load)

    def add_uniform_load(self, element_id, qx=0.0, qy=0.0, system='local'):
        self.add_member_load(UniformLoad2D(element_id, qx, qy, system))

    def add_point_load(self, element_id, position, fx=0.0, fy=0.0, system='local'):
        self.add_member_load(PointLoad2D(element_id, position, fx, fy, system))

    def add_linear_load(self, element_id, qx_i=0.0, qy_i=0.0,
                        qx_j=0.0, qy_j=0.0, system='local'):
        """Add a full-length trapezoidal/triangular line load (N/m)."""
        self.add_member_load(LinearLoad2D(element_id, qx_i, qy_i, qx_j, qy_j, system))


class DOFManager:
    """Assign only DOFs actually needed by elements at each node.

    Frame2D needs (ux,uy,rz), Truss2D (ux,uy), and Beam2D (uy,rz).
    At mixed nodes use the union of DOFs. Only a released Frame2D end is
    rotationally disconnected; a connected Beam2D end always retains rz.
    """
    def __init__(self, model):
        used = {nid: set() for nid in model.nodes}
        rotationally_connected = set()
        released_frame_nodes = set()
        for element in model.elements.values():
            dofs = element.local_dofs
            half = len(dofs)//2
            used[element.node_i].update(dofs[:half])
            used[element.node_j].update(dofs[half:])
            if isinstance(element, Frame2D):
                for nid, released in ((element.node_i, element.release_i),
                                      (element.node_j, element.release_j)):
                    (released_frame_nodes if released else rotationally_connected).add(nid)
            elif isinstance(element, Beam2D):
                rotationally_connected.update((element.node_i, element.node_j))
        self.mapping = {}
        for nid in sorted(model.nodes):
            # Preserve V0.1 behaviour for disconnected nodes so the solver flags them.
            dofs = used[nid] or set(DOFS)
            for dof in DOFS:
                if dof in dofs:
                    self.mapping[(nid, dof)] = len(self.mapping)
        self.ndof = len(self.mapping)
        self.inactive = {self.mapping[(nid,'rz')]
                         for nid in released_frame_nodes - rotationally_connected
                         if (nid,'rz') in self.mapping}

    def element_indices(self, element):
        half = len(element.local_dofs)//2
        return np.array([self.mapping[(nid,d)] for nid,ds in
                         ((element.node_i,element.local_dofs[:half]),
                          (element.node_j,element.local_dofs[half:]))
                         for d in ds], dtype=int)


@dataclass
class AnalysisResult:
    displacements: np.ndarray
    reactions: np.ndarray
    element_end_forces_local: dict[int,np.ndarray]
    dof_manager: DOFManager
    stiffness: np.ndarray
    load_vector: np.ndarray
    trace: dict | None
    nodal_load_vector: np.ndarray
    member_load_vector: np.ndarray
    element_equivalent_nodal_loads_local: dict[int,np.ndarray]
    element_fixed_end_forces_local: dict[int,np.ndarray]

    def displacement(self, node_id, dof):
        key = (node_id,dof)
        if key not in self.dof_manager.mapping:
            raise ValueError(f'DOF {key} is not present (truss-only nodes have no rz)')
        return float(self.displacements[self.dof_manager.mapping[key]])

    def reaction(self, node_id, dof):
        key = (node_id,dof)
        if key not in self.dof_manager.mapping:
            raise ValueError(f'DOF {key} is not present (truss-only nodes have no rz)')
        return float(self.reactions[self.dof_manager.mapping[key]])


class LinearStaticSolver:
    def __init__(self, mode=Mode.FAST):
        self.mode = Mode(mode)

    def solve(self, model):
        if not model.nodes or not model.elements:
            raise ValueError('Model must contain nodes and elements')
        dm = DOFManager(model)
        K = np.zeros((dm.ndof, dm.ndof))
        F_nodal = np.zeros(dm.ndof)
        F_member = np.zeros(dm.ndof)
        element_eq = {eid: np.zeros(len(e.local_dofs)) for eid,e in model.elements.items()}
        trace = {'dof_mapping':dict(dm.mapping), 'inactive_rotations': sorted(dm.inactive), 'elements':{}, 'assembly':[]} if self.mode == Mode.TEACHING else None

        # Group and validate member loads (also checks direct mutations of public lists).
        for load in model.member_loads:
            if not isinstance(load, (UniformLoad2D, LinearLoad2D, PointLoad2D)):
                raise TypeError('Unknown member load type')
            if load.element_id not in model.elements:
                raise ValueError(f'Member load references unknown element {load.element_id}')
            eid = load.element_id
            eq = model.elements[eid].equivalent_nodal_load(model, load)
            element_eq[eid] = _finite_array(element_eq[eid] + eq, f'Element {eid} accumulated member load')

        for element in model.elements.values():
            idx = dm.element_indices(element)
            kl = element.local_stiffness(model)
            T = element.transformation_matrix(model)
            kg = T.T @ kl @ T
            K[np.ix_(idx,idx)] += kg
            f_local = element_eq[element.id]
            f_global = _finite_array(T.T @ f_local, f'Element {element.id} global equivalent load')
            F_member[idx] += f_global
            if trace is not None:
                trace['elements'][element.id] = {
                    'indices':idx.copy(),
                    'local_stiffness':kl.copy(),
                    'transformation':T.copy(),
                    'global_stiffness':kg.copy(),
                    'equivalent_nodal_load_local':f_local.copy(),
                    'equivalent_nodal_load_global':f_global.copy(),
                    'fixed_end_forces_local':-f_local.copy(),
                }
                trace['assembly'].append({'element_id':element.id,
                    'indices':idx.copy(), 'contribution':kg.copy(),
                    'stiffness_after':K.copy(),
                    'load_contribution':f_global.copy()})

        for key, value in model.loads.items():
            model._check_dof(*key)
            value = _finite_float(value, 'Nodal load')
            if key not in dm.mapping or dm.mapping[key] in dm.inactive:
                if value != 0:
                    raise ValueError(f'DOF {key} has no rotational stiffness or is not active; check element types and rotations')
                continue
            F_nodal[dm.mapping[key]] += value
        _finite_array(F_nodal, 'Nodal load vector')
        _finite_array(F_member, 'Member load vector')
        F = _finite_array(F_nodal + F_member, 'Total external load vector')
        fixed_lookup = {}
        for key, value in model.constraints.items():
            model._check_dof(*key)
            value = _finite_float(value, 'Prescribed displacement')
            if key not in dm.mapping or dm.mapping[key] in dm.inactive:
                if value != 0:
                    raise ValueError(f'DOF {key} is inactive; cannot prescribe a nonzero rotation')
                continue
            fixed_lookup[dm.mapping[key]] = value
        fixed = np.array(sorted(fixed_lookup), dtype=int)
        free = np.array(sorted(set(range(dm.ndof)) - set(fixed) - dm.inactive), dtype=int)
        d = np.zeros(dm.ndof)
        d[fixed] = [fixed_lookup[i] for i in fixed]
        Kff = K[np.ix_(free, free)]
        rhs = F[free] - K[np.ix_(free,fixed)] @ d[fixed]
        _finite_array(K, 'Global stiffness matrix')
        _finite_array(rhs, 'Reduced right-hand side')
        if free.size:
            keys = {index: key for key, index in dm.mapping.items()}
            _check_reduced_stiffness(Kff, [keys[index] for index in free])
            try:
                d[free] = np.linalg.solve(Kff, rhs)
            except np.linalg.LinAlgError as exc:
                raise ValueError('Singular stiffness matrix: check supports, mechanisms, or disconnected nodes') from exc
        _finite_array(d, 'Displacements')
        R = _finite_array(K @ d - F, 'Reactions')
        end_forces = {}
        for element in model.elements.values():
            idx = dm.element_indices(element)
            # Local resisting end forces, *including* the fixed-end force term.
            q = element.local_stiffness(model) @ (element.transformation_matrix(model) @ d[idx]) - element_eq[element.id]
            end_forces[element.id] = _finite_array(q, f'Element {element.id} resisting end force')
        if trace is not None:
            trace.update({
                'global_stiffness': K.copy(),
                'nodal_load': F_nodal.copy(),
                'member_load': F_member.copy(),
                'global_load': F.copy(),
                'free_dofs': free.copy(), 'fixed_dofs': fixed.copy(),
                'reduced_stiffness': Kff.copy(), 'reduced_rhs': rhs.copy(),
                'displacements': d.copy(), 'reactions': R.copy(),
                'element_end_forces_local': {eid:q.copy() for eid,q in end_forces.items()},
            })
        return AnalysisResult(
            d, R, end_forces, dm, K, F, trace, F_nodal, F_member,
            {eid:f.copy() for eid,f in element_eq.items()},
            {eid:-f.copy() for eid,f in element_eq.items()},
        )
