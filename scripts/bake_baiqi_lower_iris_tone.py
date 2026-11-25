"""Soften the bright underpainting beneath the original lower iris glint."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image


OPEN_POSES = ('neutral', 'half_blink', 'look_left', 'look_right')


def rgba(path):
    with Image.open(path) as image:
        result = np.array(image.convert('RGBA'))
    assert result.shape == (800, 880, 4), path
    return result


def smooth(weight):
    weight = np.clip(weight, 0., 1.)
    return weight * weight * (3. - 2. * weight)


def soften(base, pigment, lower, overlay, amount):
    rows, cols = np.indices(lower.shape)
    fade = np.zeros_like(lower)
    centres = []
    # Keep the ellipse attached to each original glint as the eye moves.
    for half in (cols < lower.shape[1] / 2, cols >= lower.shape[1] / 2):
        weights = half * lower**2
        total = weights.sum()
        assert total > 2.
        x, y = float((cols * weights).sum() / total), float((rows * weights).sum() / total)
        centres.append([x, y])
        radius = ((cols - x) / 16.)**2 + ((rows - y + .5) / 11.5)**2
        fade += smooth(1. - radius)

    brightness = pigment[..., :3] @ np.array((.2126, .7152, .0722))
    tinted = amount * fade * smooth((brightness - .48) / .27) * pigment[..., 3] * (1. - overlay)
    result = base.copy()
    color = result[..., :3] - 255. * tinted[..., None] * pigment[..., :3]
    result[..., :3] = np.rint(np.clip(color, 0., 255.)).astype(np.uint8)
    return result, centres


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--layers', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--amount', type=float, default=.11)
    args = parser.parse_args()
    assert .05 <= args.amount <= .25 and args.poses.resolve() != args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    for path in args.poses.glob('*'):
        if path.is_file():
            shutil.copyfile(path, args.out / path.name)
    report = {'amount': args.amount, 'drawables': ['ArtMesh88', 'ArtMesh103'], 'states': {}}
    for state in OPEN_POSES:
        source = rgba(args.poses / f'{state}.png')
        pigment, lower, overlay = [rgba(args.layers / f'{state}_{kind}.png').astype(np.float32) / 255.
                                   for kind in ('pigment', 'lower', 'overlay')]
        toned, centres = soften(source, pigment, lower[..., 3], overlay[..., 3], args.amount)
        changed = np.any(toned != source, axis=-1)
        assert np.array_equal(toned[..., 3], source[..., 3])
        assert not np.any(changed & (rgba(args.poses / f'{state}_iris.png')[..., 0] == 0))
        assert not np.any(changed & (overlay[..., 3] == 1.))
        y, x = np.nonzero(changed)
        assert 0 < len(x) < 1200 and 438 <= y.min() <= y.max() <= 462
        Image.fromarray(toned).save(args.out / f'{state}.png')
        report['states'][state] = {'centres': centres, 'changed_pixels': int(len(x)),
                                   'bounds': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}
    (args.out / 'lower_iris_tone.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_LOWER_IRIS_TONE', report, flush=True)


if __name__ == '__main__':
    main()
