"""Compare official Hunyuan3D-2.1 shape generation on the same Delta input.

Runs the shape stage with CPU offloading on the 10GB RTX 3080. Does not claim
that the separate PBR painting stage fits the same memory budget.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/Hunyuan3D-2.1/hy3dshape'))
os.environ['HF_HOME']=str(ROOT/'tools/models/hf-cache')
print('Initializing official Hunyuan3D-2.1 shape stage',flush=True)
import torch
from PIL import Image
from accelerate import cpu_offload
from transformers.modeling_utils import no_init_weights
from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline

torch.set_num_threads(min(8,os.cpu_count() or 8))
OUT=ROOT/'artifacts/live2d_reconstruction_21';OUT.mkdir(parents=True,exist_ok=True)
folder=ROOT/'tools/models/hunyuan-2.1/hunyuan3d-dit-v2-1'
started=time.time()
report={'status':'started','source':'Delta.zip','input':'artifacts/live2d_reconstruction/input.png',
        'model':'tencent/Hunyuan3D-2.1','offload':'image encoder and VAE loaded per stage; diffusion weights offloaded per submodule',
        'steps':30,'resolution':384,'seed':20261124,'full_jpg_used':False,'pbr_paint_stage_run':False}
def save():
    (OUT/'shape_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
save()
try:
    with no_init_weights():
        pipeline=Hunyuan3DDiTFlowMatchingPipeline.from_single_file(
            str(folder/'model.fp16.ckpt'),str(folder/'config.yaml'),
            device='cpu',dtype=torch.float16,use_safetensors=False)
    device=torch.device('cuda')
    # Keep the image encoder whole: its forward reads self.model.device, so
    # leaf-offloading it would incorrectly send the input to the meta device.
    pipeline.conditioner.to(device)
    cpu_offload(pipeline.model,execution_device=device,offload_buffers=False)
    original_encode=pipeline.encode_cond
    def encode_then_release(*args,**kwargs):
        result=original_encode(*args,**kwargs)
        pipeline.conditioner.to('cpu')
        torch.cuda.empty_cache()
        return result
    pipeline.encode_cond=encode_then_release
    original_export=pipeline._export
    def load_decoder_then_export(*args,**kwargs):
        torch.cuda.empty_cache()
        pipeline.vae.to(device)
        return original_export(*args,**kwargs)
    pipeline._export=load_decoder_then_export
    pipeline.device=device
    free,total=torch.cuda.mem_get_info()
    print('Weights loaded; free GPU GiB:',round(free/1024**3,2),'of',round(total/1024**3,2),flush=True)
    image=Image.open(ROOT/report['input']).convert('RGBA')
    mesh=pipeline(image=image,num_inference_steps=report['steps'],guidance_scale=5.5,
        octree_resolution=report['resolution'],num_chunks=6000,mc_algo='mc',output_type='trimesh',
        generator=torch.Generator(device='cuda').manual_seed(report['seed']))[0]
    assert mesh is not None and len(mesh.faces)>100
    mesh.export(OUT/'Delta_shape.glb');mesh.export(OUT/'Delta_shape.ply')
    report.update(status='shape_generated',vertices=len(mesh.vertices),faces=len(mesh.faces),
                  bounds=mesh.bounds.tolist(),elapsed_seconds=time.time()-started,
                  peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated())
    print('HUNYUAN21_SHAPE_OK',json.dumps(report),flush=True)
except Exception as exc:
    report.update(status='failed',error=str(exc),exception=type(exc).__name__,elapsed_seconds=time.time()-started)
    raise
finally:
    save()
