"""Reduce the original drawn jaw line where the 3D silhouette already defines it."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from baiqi_source_raster import SourceRaster
from bake_baiqi_eye_materials import STATES


OUTLINE = 'ArtMesh116'
CROP = (960, 600, 1840, 1400)


def source_faces():
    raster = SourceRaster(2800, 4400)
    try:
        parts = {part['id']: part for part in raster.source['parts']}

        def descendants(name):
            return {name}.union(*(descendants(child) for child in parts[name]['children']))

        face = descendants('Face') - descendants('Glasses')
        shadow = {row['id'] for row in raster.drawables if row['part'] == 'Fhair' and 'Facecolor' in row['masks']}
        result = []
        for excluded in ({'ArtMesh53'}, {'ArtMesh53', OUTLINE}):
            pixels = raster.render(face, include_drawables=shadow, exclude_drawables=excluded)
            result.append(np.asarray(Image.fromarray(pixels).crop(CROP)))
        return result
    finally:
        raster.close()


def mix_artwork(source, target, fraction):
    source, target = (pixels.astype(np.float32) / 255. for pixels in (source, target))
    a, b = source[:, 3:4], target[:, 3:4]
    alpha = a * (1 - fraction) + b * fraction
    colors = source[:, :3] * a * (1 - fraction) + target[:, :3] * b * fraction
    rgb = np.divide(colors, alpha, out=np.zeros_like(colors), where=alpha > 0)
    return np.rint(np.column_stack((rgb, alpha)) * 255).astype(np.uint8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poses', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--amount', required=True, type=float)
    args = parser.parse_args()
    if not 0 < args.amount <= 1. or args.poses.resolve() == args.out.resolve():
        parser.error('Supply an amount in (0, 1] and a separate output directory.')

    original, no_outline = source_faces()
    row = np.arange(original.shape[0])[:, None]
    fade = np.clip((row - 492.) / 16., 0., 1.)
    weight = np.broadcast_to(fade * fade * (3. - 2. * fade), original.shape[:2])
    region = np.any(original != no_outline, axis=2) & (weight > 0.)
    y, x = np.nonzero(region)
    assert len(y) and 490 <= y.min() <= y.max() <= 612 and 280 <= x.min() <= x.max() <= 600
    blend = mix_artwork(original[region], no_outline[region], args.amount * weight[region, None])
    args.out.mkdir(parents=True, exist_ok=True)
    for entry in args.poses.iterdir():
        if entry.is_file():
            shutil.copyfile(entry, args.out / entry.name)
    report = {'drawables': [OUTLINE], 'amount': args.amount, 'states': {}}
    for state in ('neutral', *STATES):
        filename = f'{state}.png'
        with Image.open(args.poses / filename) as image:
            old = np.asarray(image.convert('RGBA'))
        if not np.array_equal(old[region], original[region]):
            raise ValueError(f'{state} does not match its original jaw ArtMesh')
        new = old.copy()
        new[region] = blend
        changed = np.any(new != old, axis=2)
        report['states'][state] = int(changed.sum())
        Image.fromarray(new).save(args.out / filename)
    Image.fromarray(region.astype(np.uint8) * 255).save(args.out / 'jaw_outline_mask.png')
    (args.out / 'jaw_outline.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
