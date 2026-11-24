"""Smooth the illustrated face's lighting without changing geometry or skin."""
from mathutils import Vector

def soften_face_normals(mesh):
    mesh.data.update()
    uv=mesh.data.uv_layers.active
    normals=[n.vector.copy() for n in mesh.data.corner_normals]
    changed=0
    for polygon in mesh.data.polygons:
        if mesh.data.materials[polygon.material_index].name!='Delta_Live2D_Front':continue
        for i in polygon.loop_indices:
            u,v=uv.data[i].uv
            px=u*1400-694.5;py=(1-v)*2200-550
            radius=((px/88)**2+(py/66)**2)**.5
            t=max(0.,min(1.,(1.-radius)/.32))
            weight=t*t*(3.-2.*t)
            if weight<=0:continue
            target=Vector((px/88*.2,-1.,-py/66*.1)).normalized()
            normals[i]=(normals[i]*(1-weight)+target*weight).normalized();changed+=1
    mesh.data.normals_split_custom_set(normals)
    return changed
