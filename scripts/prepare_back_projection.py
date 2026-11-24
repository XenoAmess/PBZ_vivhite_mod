"""Infer a conservative rear color layout from Delta's own Live2D palette.

This is a procedural approximation, not an artist-provided rear reference.
Keep the source UVs so color boundaries do not follow coarse triangle edges.
"""
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
source=np.array(Image.open(ROOT/'artifacts/live2d/Delta_projection_padded.png').convert('RGB'))
h,w=source.shape[:2]
y,x=np.mgrid[:h,:w]
back=source.astype(float)
coat=np.array([67.,62.,82.])
coat_shade=1.-.055*np.cos((x-694.5)/90.)**2
body=(y>=639)&(y<1108)
back[body]=(coat[None,None,:]*coat_shade[:,:,None])[body]
# Neck and a short rear collar, with no front shirt/bow copied to the back.
neck=(y>=602)&(y<639)
back[neck]=[250,226,216]
collar=(y>=635)&(y<651)&(np.abs(x-694.5)<70)
back[collar]=[225,231,241]
hair=y<602
strands=(2.0*np.sin(x*.14)+1.3*np.sin(x*.037)+(y-380)*.008)
hair_color=np.stack([216+strands,224+strands,237+strands],axis=-1)
back[hair]=hair_color[hair]
# Retain the character's actual black-and-gold side bows.
bows=(y>425)&(y<562)&(np.abs(x-694.5)>122)&(np.abs(x-694.5)<218)
back[bows]=source[bows]
# Smooth continuous coat hem and a subdued central tailoring seam.
hem_y=1090+8*np.minimum(np.abs(x-694.5)/180.,1.)
gold=body&(np.abs(y-hem_y)<3.)
back[gold]=[224,179,35]
seam=body&(np.abs(x-694.5)<1.6)&(y>675)&(y<1080)
back[seam]=[57,52,72]
# Below the coat reuse the original skirt, stockings, boots and their palette.
ownership=np.load(ROOT/'artifacts/live2d/arm_ownership.npy')
arms=(ownership>.5)&(y>735)
back[arms]=source[arms]
# New finger geometry has no source-image UV. Reserve a hidden texture swatch.
back[h-60:h,w-60:w]=[250,231,220]
out=ROOT/'artifacts/live2d/Delta_back_inferred.png'
Image.fromarray(np.clip(back,0,255).astype('uint8')).save(out)
print('INFERRED_BACK_PROJECTION',out)
