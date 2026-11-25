"""Remove the inherited planar neck tint from the projected lower face."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from baiqi_source_raster import SourceRaster
from bake_baiqi_eye_materials import STATES
from bake_baiqi_jaw_outline import CROP, OUTLINE


NECK_TINT = {'ArtMesh115', 'ArtMesh233'}


def source_region():
    raster = SourceRaster(2800, 4400)
    try:
        parts = {part['id']: part for part in raster.source['parts']}

        def descendants(name):
            return {name}.union(*(descendants(child) for child in parts[name]['children']))

        face = descendants('Face') - descendants('Glasses')
        shadow = {row['id'] for row in raster.drawables if row['part'] == 'Fhair' and 'Facecolor' in row['masks']}
        layers = []
        for omit in (set(), NECK_TINT):
            frame = raster.render(face, include_drawables=shadow, exclude_drawables=omit | {'ArtMesh53', OUTLINE})
            layers.append(np.asarray(Image.fromarray(frame).crop(CROP)))
        return layers
    finally:
        raster.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--amount', type=float, required=True)
    args = parser.parse_args()
    if not 0 < args.amount <= 1. or args.poses.resolve() == args.out.resolve():
        parser.error('Supply an amount in (0, 1] and a separate output directory.')

    attached, hidden = source_region()
    affected = np.any(attached != hidden, axis=2)
    affected[:567] = False
    rows, cols = np.nonzero(affected)
    assert len(rows) and 380 <= cols.min() <= cols.max() <= 450 and 572 <= rows.min() <= rows.max() <= 620
    swatch = attached[520, 432, :3]
    assert np.array_equal(swatch, attached[590, 433, :3]) and attached[520, 432, 3] == 255
    target = np.where(hidden[affected, 3:4] > 0, hidden[affected, :3], swatch)
    original = attached[affected, :3].astype(np.float32)
    color = np.rint(original + args.amount * (target.astype(np.float32) - original)).astype(np.uint8)

    args.out.mkdir(parents=True, exist_ok=True)
    for item in args.poses.iterdir():
        if item.is_file():
            shutil.copyfile(item, args.out / item.name)
    report = {'drawables': sorted(NECK_TINT), 'amount': args.amount, 'skin_rgb': swatch.tolist(), 'states': {}}
    for state in ('neutral', *STATES):
        filename = f'{state}.png'
        with Image.open(args.poses / filename) as image:
            previous = np.asarray(image.convert('RGBA'))
        assert np.array_equal(previous[affected], attached[affected]), state
        corrected = previous.copy()
        corrected[affected, :3] = color
        report['states'][state] = int(np.sum(np.any(corrected != previous, axis=2)))
        Image.fromarray(corrected).save(args.out / filename)
    Image.fromarray(affected.astype(np.uint8) * 255).save(args.out / 'underjaw_tint_mask.png')
    (args.out / 'underjaw_tint.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
