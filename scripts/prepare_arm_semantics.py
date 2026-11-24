from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
ROOT=Path(__file__).resolve().parents[1]
arms=np.array(Image.open(ROOT/'artifacts/live2d/Delta_arms_mask.png'))>127
alpha=np.array(Image.open(ROOT/'artifacts/live2d/Delta_front.png'))[:,:,3]
body=(alpha>127)&~arms
distance_arms=distance_transform_edt(~arms);distance_body=distance_transform_edt(~body)
ownership=np.clip(.5+(distance_body-distance_arms)/32.,0,1)
ownership=ownership*ownership*(3-2*ownership)
ownership[arms]=1.;ownership[body]=0.
shoulder=np.clip((np.arange(2200)[:,None]-700)/50.,0,1)
ownership*=shoulder*shoulder*(3-2*shoulder)
np.save(ROOT/'artifacts/live2d/arm_ownership.npy',ownership.astype(np.float32))
np.save(ROOT/'artifacts/live2d/source_opacity.npy',alpha.astype(np.float32)/255)
print('CUBISM_SEMANTICS_PREPARED',int(arms.sum()))
