"""Anatomical directions validated against selected original Soul poses."""
import json
from pathlib import Path
def finger_flexion(side):
    data=json.loads((Path(__file__).parent/'native_finger_axes.json').read_text(encoding='utf-8'))
    return tuple(data['vectors'][side])

def thumb_grip(name):
    data=json.loads((Path(__file__).parent/'native_thumb_grip.json').read_text(encoding='utf-8'))
    return tuple(data['local_rotation_quaternions'][name])
