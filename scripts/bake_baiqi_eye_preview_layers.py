"""Extract four original eye poses and preserve every non-eye atlas pixel."""
import argparse
from pathlib import Path
import ctypes as c
import json
import sys

import numpy as np
from PIL import Image, ImageFilter

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))
from baiqi_source_raster import SourceRaster

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inputs', type=Path, required=True, help='Game export containing form_inputs.json.')
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--lower-glint-opacity', default=1., type=float,
                    help='Scale the original paired lower iris glint layers.')
args = parser.parse_args()
assert .35 <= args.lower_glint_opacity <= 1.


class V2(c.Structure):
    _fields_ = [('x', c.c_float), ('y', c.c_float)]


core = c.CDLL(str(root / 'tools/cubism_core/Live2DCubismCore.dll'))


def call(name, result, types, *args):
    fn = getattr(core, 'csm' + name)
    fn.restype = result
    fn.argtypes = types
    return fn(*args)


vp, uint = c.c_void_p, c.c_uint
moc_bytes = (root / 'source/Delta/Delta.moc3').read_bytes()
storage = c.create_string_buffer(len(moc_bytes) + 63)
address = (c.addressof(storage) + 63) & ~63
c.memmove(address, moc_bytes, len(moc_bytes))
moc = call('ReviveMocInPlace', vp, (vp, uint), address, len(moc_bytes))
assert moc
size = call('GetSizeofModel', uint, (vp,), moc)
working = c.create_string_buffer(size + 15)
address = (c.addressof(working) + 15) & ~15
model = call('InitializeModelInPlace', vp, (vp, vp, uint), moc, address, size)
assert model


def array(name, dtype):
    return call('Get' + name, c.POINTER(dtype), (vp,), model)


source = SourceRaster(2800, 4400)
parts = {p['id']: p for p in source.source['parts']}


def descendants(name):
    return {name}.union(*(descendants(child) for child in parts[name]['children']))


face = descendants('Face') - {'Glasses'}
shadow = {row['id'] for row in source.drawables if row['part'] == 'Fhair' and 'Facecolor' in row['masks']}
parameters = {row['id']: i for i, row in enumerate(source.source['parameters'])}
param_ids = array('ParameterIds', c.c_char_p)
assert all(param_ids[idx].decode() == name for name, idx in parameters.items())
values, defaults = (array('Parameter' + name + 'Values', c.c_float) for name in ('', 'Default'))
xy = array('DrawableVertexPositions', c.POINTER(V2))
opacity = array('DrawableOpacities', c.c_float)
orders = array('RenderOrders', c.c_int)
crop = (960, 600, 1840, 1400)
lower_glints = {'ArtMesh85', 'ArtMesh94'}


def face_at(parameters_override, glint=1.):
    for i in parameters.values():
        values[i] = defaults[i]
    for key, value in parameters_override.items():
        values[parameters[key]] = value
    call('UpdateModel', None, (vp,), model)
    overrides = [dict(id=row['id'], positions_xy=[[v.x, v.y] for v in xy[i][:len(row['positions_xy'])]],
                      opacity=opacity[i], render_order=orders[i])
                 for i, row in enumerate(source.source['drawables'])]
    source.set_state({'draw_overrides': overrides})
    eyes = source.render(descendants('Eyes'), exclude_drawables={'ArtMesh53'})
    mask = Image.fromarray(eyes).crop(crop).getchannel('A').filter(ImageFilter.GaussianBlur(.45))
    if glint != 1.:
        for row in overrides:
            if row['id'] in lower_glints:
                row['opacity'] *= glint
        source.set_state({'draw_overrides': overrides})
    picture = source.render(face, include_drawables=shadow, exclude_drawables={'ArtMesh53'})
    return np.array(Image.fromarray(picture).crop(crop)), mask


def transfer(original, neutral, posed, name):
    changed = np.max(np.abs(posed.astype(np.int16) - neutral), axis=-1) > 2
    y, x = np.nonzero(changed)
    if not len(x):
        assert name == 'neutral'
        return original, {'changed_pixels': 0, 'rect': None}
    assert x.min() >= 280 and x.max() <= 600 and y.min() >= 375 and y.max() <= 465, name
    result = original.copy()
    result[changed] = posed[changed]
    return result, {'changed_pixels': int(changed.sum()),
                    'rect': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}


inputs = root / args.inputs
form = json.loads((inputs / 'form_inputs.json').read_text())['coat_off']
entry = form['materials']['BaiQi original face appearance']['images'][0]['path']
with Image.open(inputs / entry) as image:
    original = np.array(image.convert('RGBA'))
neutral, _ = face_at({})
assert original.shape == neutral.shape == (800, 880, 4)
states = {'half_blink': {'ParamEyeLOpen': .5, 'ParamEyeROpen': .5},
          'closed': {'ParamEyeLOpen': 0., 'ParamEyeROpen': 0.},
          'look_left': {'ParamEyeBallX': -.65}, 'look_right': {'ParamEyeBallX': .65}}
out = root / args.out
out.mkdir(parents=True, exist_ok=True)
if args.lower_glint_opacity == 1.:
    Image.fromarray(original).save(out / 'neutral.png')
else:
    softer, _ = face_at({}, args.lower_glint_opacity)
    result, measured = transfer(original, neutral, softer, 'neutral')
    assert measured['changed_pixels'] > 0
    Image.fromarray(result).save(out / 'neutral.png')
    (out / 'glint.json').write_text(json.dumps({'opacity_scale': args.lower_glint_opacity,
                                                'drawables': sorted(lower_glints), **measured}, indent=2) + '\n')
report = {}
for name, override in states.items():
    posed, mask = face_at(override, args.lower_glint_opacity)
    result, measured = transfer(original, neutral, posed, name)
    Image.fromarray(result).save(out / (name + '.png'))
    mask.save(out / (name + '_mask.png'))
    report[name] = {'parameters': override, **measured}
(out / 'probe.json').write_text(json.dumps(report, indent=2))
source.close()
print(report, flush=True)
