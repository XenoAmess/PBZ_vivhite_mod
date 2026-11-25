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
parser.add_argument('--iris-pigment', default=1., type=float,
                    help='Scale the RGB multiply colour of the two original pink iris layers.')
parser.add_argument('--sclera-tone', default=1., type=float,
                    help='Scale the original eye whites near the upper lids, using their Cubism coverage.')
parser.add_argument('--previous-poses', type=Path,
                    help='Apply the eye-white adjustment to the approved five pose images.')
parser.add_argument('--iris-masks', action='store_true', help='Export the original clipped iris coverage for each pose.')
args = parser.parse_args()
assert .35 <= args.lower_glint_opacity <= 1.
assert .75 <= args.iris_pigment <= 1.
assert .82 <= args.sclera_tone <= 1.
if args.sclera_tone != 1. and args.previous_poses is None:
    parser.error('--sclera-tone requires --previous-poses')


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
irises = {'ArtMesh88', 'ArtMesh103'}
sclera = {'ArtMesh90', 'ArtMesh93'}


def crop_raster(picture):
    return Image.fromarray(picture).crop(crop)


def lid_shading(original, shaded, whites, iris):
    opaque = np.asarray(whites) >= 64
    top = opaque.argmax(axis=0)
    y = np.arange(opaque.shape[0])[:, None]
    weight = (.27 + .73 * np.exp(-.5 * ((y - top) / 5.4) ** 2)) * opaque.any(axis=0)
    weight[np.asarray(iris) >= 250] = 0.
    base, toned = (np.asarray(image, dtype=np.float32) for image in (original, shaded))
    assert np.array_equal(base[..., 3], toned[..., 3])
    return np.rint(base + weight[..., None] * (toned - base)).astype(np.uint8)


def face_at(parameters_override, glint=1., pigment=1., *, sclera_tone=1.):
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
    mask = crop_raster(eyes).getchannel('A').filter(ImageFilter.GaussianBlur(.45))
    iris = None
    if args.iris_masks or args.sclera_tone != 1.:
        coverage = source.render(set(), include_drawables=irises)
        iris = crop_raster(coverage).getchannel('A').filter(ImageFilter.GaussianBlur(.60))
    if glint != 1. or pigment != 1.:
        for row in overrides:
            if row['id'] in lower_glints:
                row['opacity'] *= glint
            if row['id'] in irises and pigment != 1.:
                red, green, blue, alpha = source.by_id[row['id']]['multiply_color']
                row['multiply_color'] = [red * pigment, green * pigment, blue * pigment, alpha]
        source.set_state({'draw_overrides': overrides})
    picture = np.array(crop_raster(source.render(face, include_drawables=shadow, exclude_drawables={'ArtMesh53'})))
    whites = None
    if sclera_tone != 1.:
        whites = crop_raster(source.render(set(), include_drawables=sclera)).getchannel('A')
        for row in overrides:
            if row['id'] in sclera:
                red, green, blue, alpha = source.by_id[row['id']]['multiply_color']
                row['multiply_color'] = [red * sclera_tone, green * sclera_tone, blue * sclera_tone, alpha]
        source.set_state({'draw_overrides': overrides})
        shaded = crop_raster(source.render(face, include_drawables=shadow, exclude_drawables={'ArtMesh53'}))
        return lid_shading(picture, shaded, whites, iris), mask, iris, whites, picture
    return picture, mask, iris, whites, picture


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


def sclera_delta(state, posed, unshaded):
    with Image.open(root / args.previous_poses / f'{state}.png') as previous:
        approved = np.array(previous.convert('RGBA'))
    assert approved.shape == posed.shape == unshaded.shape
    if state == 'neutral':
        assert np.array_equal(approved, original)
    delta = posed.astype(np.int16) - unshaded
    assert not delta[..., 3].any()
    adjusted = np.clip(approved.astype(np.int16) + delta, 0, 255).astype(np.uint8)
    return transfer(approved, approved, adjusted, state) if state != 'closed' else (
        approved, {'changed_pixels': 0, 'rect': None})


inputs = root / args.inputs
form = json.loads((inputs / 'form_inputs.json').read_text())['coat_off']
entry = form['materials']['BaiQi original face appearance']['images'][0]['path']
with Image.open(inputs / entry) as image:
    original = np.array(image.convert('RGBA'))
neutral, _, neutral_iris, _, _ = face_at({})
assert original.shape == neutral.shape == (800, 880, 4)
states = {'half_blink': {'ParamEyeLOpen': .5, 'ParamEyeROpen': .5},
          'closed': {'ParamEyeLOpen': 0., 'ParamEyeROpen': 0.},
          'look_left': {'ParamEyeBallX': -.65}, 'look_right': {'ParamEyeBallX': .65}}
out = root / args.out
out.mkdir(parents=True, exist_ok=True)
if neutral_iris is not None:
    neutral_iris.save(out / 'neutral_iris.png')
if args.lower_glint_opacity == args.iris_pigment == args.sclera_tone == 1.:
    Image.fromarray(original).save(out / 'neutral.png')
else:
    softer, _, _, neutral_whites, unshaded = face_at({}, args.lower_glint_opacity, args.iris_pigment,
                                                       sclera_tone=args.sclera_tone)
    if neutral_whites is not None:
        result, measured = sclera_delta('neutral', softer, unshaded)
    else:
        result, measured = transfer(original, neutral, softer, 'neutral')
    assert measured['changed_pixels'] > 0
    Image.fromarray(result).save(out / 'neutral.png')
    (out / 'glint.json').write_text(json.dumps({'opacity_scale': args.lower_glint_opacity,
                                                'drawables': sorted(lower_glints), **measured}, indent=2) + '\n')
    if neutral_whites is not None:
        neutral_whites.save(out / 'neutral_sclera.png')
if args.iris_pigment != 1.:
    (out / 'iris_pigment.json').write_text(json.dumps({'rgb_scale': args.iris_pigment,
                                                       'drawables': sorted(irises)}, indent=2) + '\n')
if args.sclera_tone != 1.:
    (out / 'sclera_depth.json').write_text(json.dumps({'rgb_scale': args.sclera_tone,
                                                       'drawables': sorted(sclera)}, indent=2) + '\n')
report = {}
for name, override in states.items():
    pigment = 1. if name == 'closed' else args.iris_pigment
    sclera_tone = 1. if name == 'closed' else args.sclera_tone
    posed, mask, iris, whites, unshaded = face_at(override, args.lower_glint_opacity, pigment, sclera_tone=sclera_tone)
    if args.sclera_tone != 1.:
        result, measured = sclera_delta(name, posed, unshaded)
    else:
        result, measured = transfer(original, neutral, posed, name)
    Image.fromarray(result).save(out / (name + '.png'))
    mask.save(out / (name + '_mask.png'))
    if iris is not None:
        if name == 'closed':
            # The underlying iris ArtMeshes still exist during a full blink.
            # Their material coverage is hidden by the closed eyelids.
            iris = Image.new('L', iris.size, 0)
        iris.save(out / (name + '_iris.png'))
    if args.sclera_tone != 1.:
        (whites if whites is not None else Image.new('L', mask.size, 0)).save(out / f'{name}_sclera.png')
    report[name] = {'parameters': override, **measured}
(out / 'probe.json').write_text(json.dumps(report, indent=2))
source.close()
print(report, flush=True)
