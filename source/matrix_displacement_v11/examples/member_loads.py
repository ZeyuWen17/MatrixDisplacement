"""V0.2 demonstration: a fixed-base cantilever under member loads."""
from matrix_displacement import (
    Node, Material, Section, Frame2D, StructuralModel,
    LinearStaticSolver, Mode,
)

m = StructuralModel()
m.add_node(Node(1,0,0))
m.add_node(Node(2,4,0))
m.add_material(Material(1,210e9))
m.add_section(Section(1,0.015,8e-6))
m.add_element(Frame2D(1,1,2,1,1))
for dof in ('ux','uy','rz'):
    m.constrain(1,dof)

# Uniform load 1,200 N/m downward over the member.
m.add_uniform_load(1, qy=-1200.0)
# Point load 700 N downward, 1.7 m from the fixed node.
m.add_point_load(1, position=1.7, fy=-700.0)

result = LinearStaticSolver(Mode.TEACHING).solve(m)
print('Node 2 vertical displacement (m):',result.displacement(2,'uy'))
print('Support vertical reaction (N):',result.reaction(1,'uy'))
print('Support reaction moment (N m):',result.reaction(1,'rz'))
print('Element equivalent nodal load, LOCAL:',result.element_equivalent_nodal_loads_local[1])
print('Element fixed-end forces, LOCAL:',result.element_fixed_end_forces_local[1])
print('Element resisting end forces, LOCAL:',result.element_end_forces_local[1])
print('Teaching trace keys:',list(result.trace.keys()))
