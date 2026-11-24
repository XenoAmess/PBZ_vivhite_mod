"""Replace fused inferred fingers with geometry built around the native joints.

Creates new palm/finger surfaces; does not copy the original game's hand mesh.
The original bone names and transforms are kept intact.
"""
import math
import bpy
import bmesh
from mathutils import Vector


def repair_hands(mesh,arm):
    def point(name):return arm.matrix_world@arm.data.bones[name].head_local
    bm=bmesh.new();bm.from_mesh(mesh.data)
    deform=bm.verts.layers.deform.verify()
    uv=bm.loops.layers.uv.active
    groups={g.name:g.index for g in mesh.vertex_groups}
    def group(name):
        if name not in groups:groups[name]=mesh.vertex_groups.new(name=name).index
        return groups[name]
    before=len(bm.verts)
    hands={}
    for side,sign in [('l',1),('r',-1)]:
        wrist=point('hand_'+side)
        bases=[point(f'{finger}_01_{side}') for finger in ['index','middle','ring','pinky']]
        knuckles=sum(bases,Vector())/4
        direction=(knuckles-wrist).normalized()
        width=(bases[0]-bases[-1]).normalized()
        width=(width-direction*width.dot(direction)).normalized()
        normal=direction.cross(width).normalized()
        # Restrict the cut to the hand's original source-image region; the
        # same plane can otherwise intersect clothing or the other limb.
        region=set()
        for vertex in bm.verts:
            if not vertex.link_loops:continue
            source_uv=vertex.link_loops[0][uv].uv
            px=source_uv.x*1400;py=(1-source_uv.y)*2200
            if sign*(px-694.5)>280 and py>1005:region.add(vertex)
        geometry=set(region)
        for vertex in region:
            geometry.update(vertex.link_edges);geometry.update(vertex.link_faces)
        bmesh.ops.bisect_plane(bm,geom=list(geometry),dist=1e-6,
                              plane_co=wrist-direction*.003,plane_no=direction,
                              clear_outer=True,clear_inner=False)
        generated=[]
        def vertex(position,weights):
            v=bm.verts.new(position)
            total=sum(weights.values())
            for name,w in weights.items():v[deform][group(name)]=w/total
            generated.append(v);return v
        def face(vs):
            f=bm.faces.new(vs);f.material_index=6;f.smooth=True
            for loop in f.loops:loop[uv].uv=(.70,.51)
            return f
        def connect(a,b):
            for j in range(len(a)):face([a[j],a[(j+1)%len(a)],b[(j+1)%len(b)],b[j]])
        def cap(ring,center,weights,reverse=False):
            c=vertex(center,weights)
            for j in range(len(ring)):
                vs=[ring[j],ring[(j+1)%len(ring)],c]
                face(vs[::-1] if reverse else vs)
        # The palm has rounded rectangular cross sections and overlaps the
        # retained wrist by 8 mm, underneath the existing wrist band.
        length=(knuckles-wrist).length
        half_width=(bases[0]-bases[-1]).length*.5+.008
        palm=[]
        for t,rx,ry in [(-.08,.023,.014),(.12,.026,.016),(.55,half_width*.95,.018),(.90,half_width,.016),(1.02,half_width*.92,.012)]:
            center=wrist+direction*(length*t)
            ring=[]
            for j in range(16):
                angle=2*math.pi*j/16
                pos=center+width*(rx*math.cos(angle))+normal*(ry*math.sin(angle))
                weights={'hand_'+side:1.}
                if t<.15:
                    forearm=max(0.,.3*(.15-t)/.23)
                    weights={'hand_'+side:1-forearm,'lowerarm_twist_01_'+side:forearm}
                ring.append(vertex(pos,weights))
            if palm:connect(palm[-1],ring)
            palm.append(ring)
        cap(palm[0],wrist-direction*.008,{'hand_'+side:1.},True)
        cap(palm[-1],wrist+direction*length*1.02,{'hand_'+side:1.})
        # Multiple rings around each joint give bending an actual edge loop.
        for finger,radius in [('thumb',.010),('index',.009),('middle',.0095),('ring',.0088),('pinky',.0075)]:
            names=[f'{finger}_{i:02}_{side}' for i in [1,2,3]]
            points=[point(n) for n in names]
            tip=points[-1]+(points[-1]-points[-2])*.62
            points.append(tip)
            rings=[]
            for segment in range(3):
                for t in [0.,.15,.5,.85]:
                    center=points[segment].lerp(points[segment+1],t)
                    tangent=(points[segment+1]-points[segment]).normalized()
                    u=normal-tangent*normal.dot(tangent)
                    if u.length<.1:u=width-tangent*width.dot(tangent)
                    u.normalize();v=tangent.cross(u).normalized()
                    phase=segment+t
                    r=radius*(1-.16*phase)
                    weights={names[segment]:1.}
                    if t<.15 and segment>0:
                        blend=.5*(1-t/.15);weights={names[segment]:1-blend,names[segment-1]:blend}
                    elif t>.85 and segment<2:
                        blend=.5*(t-.85)/.15;weights={names[segment]:1-blend,names[segment+1]:blend}
                    elif segment==0 and t==0:
                        weights={names[0]:.65,'hand_'+side:.35}
                    ring=[vertex(center+u*(r*math.cos(2*math.pi*j/12))+v*(r*math.sin(2*math.pi*j/12)),weights) for j in range(12)]
                    if rings:connect(rings[-1],ring)
                    rings.append(ring)
            cap(rings[0],points[0],{names[0]:1.},True)
            cap(rings[-1],tip,{names[-1]:1.})
        hands[side]={'generated_vertices':len(generated),'finger_chains':5,'copied_game_geometry':False}
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh.data);bm.free();mesh.data.update()
    return {'method':'new palm and finger edge loops around native joint centers',
            'vertices_before':before,'vertices_after':len(mesh.data.vertices),'hands':hands,
            'limits':['Wrist overlap is concealed by band, not a welded production topology',
                      'Procedural hands still need visual and live weapon-grip review']}
