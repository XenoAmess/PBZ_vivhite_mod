"""Register the two original nose paint layers to the approved 3D face."""
import argparse
import json
from pathlib import Path
from shutil import copyfile

import numpy as np
from PIL import Image

from baiqi_source_raster import SourceRaster


LAYERS = {'Nose2', 'ArtMesh106'}
CROP = (960, 600, 1840, 1400)
STATES = ('neutral', 'half_blink', 'closed', 'look_left', 'look_right')
SHIFT = (-9, 8)


def nose_delta():
    source = SourceRaster(2800, 4400)
    parts = {part['id']: part for part in source.source['parts']}

    def descendants(name):
        return {name}.union(*(descendants(child) for child in parts[name]['children']))

    face = descendants('Face') - {'Glasses'}
    shadow = {row['id'] for row in source.drawables if row['part'] == 'Fhair' and 'Facecolor' in row['masks']}
    try:
        base = source.render(face, include_drawables=shadow, exclude_drawables={'ArtMesh53'})
        horizontal = SHIFT[0] * 2 / (source.width * source.mvp[0])
        vertical = -SHIFT[1] * 2 / (source.height * source.mvp[5])
        overrides = [{'id': row['id'], 'positions_xy': [[x + horizontal, y + vertical] for x, y in row['positions_xy']]}
                     for row in source.drawables if row['id'] in LAYERS]
        assert {row['id'] for row in overrides} == LAYERS
        source.set_state({'draw_overrides': overrides})
        moved = source.render(face, include_drawables=shadow, exclude_drawables={'ArtMesh53'})
    finally:
        source.close()
    previous, aligned = (np.array(Image.fromarray(image).crop(CROP), dtype=np.int16) for image in (base, moved))
    delta = aligned - previous
    assert not delta[..., 3].any()
    y, x = np.nonzero(np.any(delta != 0, axis=-1))
    assert 398 <= x.min() <= x.max() <= 467 and 440 <= y.min() <= y.max() <= 511
    return delta, {'drawables': sorted(LAYERS), 'offset_pixels': SHIFT, 'changed_pixels': len(x),
                   'bounds': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poses', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    assert args.poses.resolve() != args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    delta, report = nose_delta()
    for state in STATES:
        with Image.open(args.poses / f'{state}.png') as image:
            base = np.array(image.convert('RGBA'), dtype=np.int16)
        assert base.shape == delta.shape
        Image.fromarray(np.clip(base + delta, 0, 255).astype(np.uint8)).save(args.out / f'{state}.png')
        for suffix in ('iris', 'mask', 'sclera'):
            path = args.poses / f'{state}_{suffix}.png'
            if path.is_file():
                copyfile(path, args.out / path.name)
    glint = args.poses / 'glint.json'
    if glint.is_file():
        copyfile(glint, args.out / glint.name)
    (args.out / 'nose_registration.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
