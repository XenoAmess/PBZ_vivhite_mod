"""Author side/rear bob clumps around the source-derived front fringe."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_component_assembly_004/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_005');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.candidate));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');controller=bpy.data.objects['BaiQi_Source_State_Controller'];collection=next(c for c in bpy.data.collections if c.name.startswith('BaiQi Bhair '));source_parts=set()
for obj in list(bpy.data.objects):
    if obj.name=='BaiQi rounded rear hair' or obj.name.startswith('BaiQi side hair continuation'):
        source_parts.update(json.loads(obj.get('baiqi_source_parts','[]')));bpy.data.objects.remove(obj,do_unlink=True)
mat=bpy.data.materials['BaiQi side hair source color'];shape=np.array([(165,10.7,8.5),(170,13.5,11),(178,15.1,12.2),(186,14.5,11.8),(191,12,9.5),(194,8.3,6.7),(196,.1,.1)])
def profile(z,k):
    i=max(0,min(len(shape)-2,int(np.searchsorted(shape[:,0],z)-1)));a,b=shape[i:i+2];t=float(np.clip((z-a[0])/(b[0]-a[0]),0,1));h=b[0]-a[0]
    slope=lambda j:(shape[min(len(shape)-1,j+1),k]-shape[max(0,j-1),k])/(shape[min(len(shape)-1,j+1),0]-shape[max(0,j-1),0])
    return (2*t**3-3*t*t+1)*a[k]+(t**3-2*t*t+t)*h*slope(i)+(-2*t**3+3*t*t)*b[k]+(t**3-t*t)*h*slope(i+1)
records=[]
for index,angle in enumerate(np.linspace(-.43,math.pi+.43,23)):
    vertices=[];faces=[];n=48;across=9;tip=165.4+2.0*max(0,math.sin(angle))+.4*math.cos(index*2.4)
    for row,t in enumerate(np.linspace(0,1,n)):
        z=195.5*(1-t)+tip*t;rx,ry=profile(z,1),profile(z,2);width=.125*(.55+.45*math.sin(math.pi*t))*(1 if t<.87 else max(.018,(1-t)/.13))
        for s in np.linspace(-1,1,across):
            phi=angle+s*width;bulge=.47*math.sqrt(max(0,1-s*s))*math.sin(math.pi*t*.87);vertices.append(((rx+bulge)*math.cos(phi),6.7+(ry+bulge)*math.sin(phi),z))
    for row in range(n-1):
        for j in range(across-1):k=row*across+j;faces.append((k,k+1,k+1+across,k+across))
    data=bpy.data.meshes.new('BaiQi rear hair clump '+str(index));data.from_pydata(vertices,[],faces);data.materials.append(mat);uv=data.uv_layers.new(name='BaiQiCanvas');scale=195/1607
    for poly in data.polygons:
        poly.use_smooth=True
        for li in poly.loop_indices:
            co=data.vertices[data.loops[li].vertex_index].co;uv.data[li].uv=((co.x*.86/scale+694.5)/1400,1-(600-(co.z-165.35)/scale)/2200)
    obj=bpy.data.objects.new(data.name,data);collection.objects.link(obj);obj.parent=arm;obj.vertex_groups.new(name='head').add(list(range(len(data.vertices))),1,'REPLACE');mod=obj.modifiers.new('Hair clump volume','SOLIDIFY');mod.thickness=.36;mod.offset=0;mod=obj.modifiers.new('Native adult head','ARMATURE');mod.object=arm;obj['baiqi_source_parts']=json.dumps(sorted(source_parts));obj['inferred_geometry']='Side and rear clump continuation inferred from original bob silhouette'
    # Original alternate ponytail state uses a shorter back silhouette.
    for prop in ['hide_render','hide_viewport']:
        driver=obj.driver_add(prop).driver;v=driver.variables.new();v.name='state';v.targets[0].id=controller;v.targets[0].data_path='["source_state"]';driver.expression='state==20'
    records.append(obj.name)
path=out/'BaiQi_Assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));(out/'hair_clump_report.json').write_text(json.dumps({'status':'pending_visual_review','model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_candidate':args.candidate,'clumps':records,'source_parts':sorted(source_parts),'note':'Front hair shadows are baked on the face and are not physical hair geometry.'},indent=2));print('BAIQI_BACK_HAIR_CLUMPS',len(records),flush=True)
