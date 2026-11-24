"""Create constant color/normal/ARM data textures for native game materials."""
import json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'artifacts/native_material_inputs';out.mkdir(exist_ok=True)
data=json.loads((ROOT/'build/model_inputs/inputs.json').read_text())['adult']['materials']
colors={name:spec['color'][:3] for name,spec in data.items() if not spec['front_texture']}
colors['DeltaReserved']=[0.,0.,0.]
for name,values in colors.items():
    def encode(value):return round(255*(12.92*value if value<=.0031308 else 1.055*value**(1/2.4)-.055))
    Image.new('RGB',(64,64),tuple(encode(c) for c in values)).save(out/(name+'.png'))
Image.new('RGB',(64,64),(128,128,255)).save(out/'FlatNormal.png')
Image.new('RGB',(64,64),(255,255,0)).save(out/'MatteARM.png')
# Unreal disables VT for a non-power-of-two source even when the cooked size
# uses STRETCH_TO_POWER_OF_TWO. Resample the input itself before importing.
with Image.open(ROOT/'artifacts/live2d/Delta_projection_padded.png') as source:
    source.convert('RGB').resize((2048,4096),Image.Resampling.LANCZOS).save(out/'ProjectionPOT.png')
with Image.open(ROOT/'artifacts/live2d/Delta_back_inferred.png') as source:
    source.convert('RGB').resize((2048,4096),Image.Resampling.LANCZOS).save(out/'BackProjectionPOT.png')
print('NATIVE_MATERIAL_INPUTS',len(colors)+2)
