from matrix_displacement import *

model = StructuralModel()
model.add_node(Node(1, 0.0, 0.0))
model.add_node(Node(2, 3.0, 0.0))
model.add_material(Material(1, 210e9))
model.add_section(Section(1, 0.01, 8e-6))
model.add_element(Frame2D(1, 1, 2, 1, 1))
for dof in ('ux','uy','rz'):
    model.constrain(1,dof)
model.add_load(2,'uy',-1000.0)

result = LinearStaticSolver(Mode.TEACHING).solve(model)
print('DOF mapping:', result.dof_manager.mapping)
print('Node 2 uy (m):', result.displacement(2,'uy'))
print('Node 2 rz (rad):', result.displacement(2,'rz'))
print('Support vertical reaction (N):', result.reaction(1,'uy'))
print('Local element end forces:', result.element_end_forces_local[1])
print('Local stiffness matrix:\n', result.trace['elements'][1]['local_stiffness'])
