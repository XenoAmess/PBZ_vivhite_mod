"""Transfer Adult Soul joint motion onto the original CC0 armature for review."""
import math

from mathutils import Matrix, Quaternion


SOUL_TO_CC0 = Quaternion((0, 0, 1), math.pi)
CENTER = {
    'Root': 'root',
    'J_Bip_C_Hips': 'pelvis',
    'J_Bip_C_Spine': 'spine_01',
    'J_Bip_C_Chest': 'spine_03',
    'J_Bip_C_UpperChest': 'spine_05',
    'J_Bip_C_Neck': 'neck_02',
    'J_Bip_C_Head': 'head',
}
LIMB = {
    'Shoulder': 'clavicle', 'UpperArm': 'upperarm', 'LowerArm': 'lowerarm', 'Hand': 'hand',
    'UpperLeg': 'thigh', 'LowerLeg': 'calf', 'Foot': 'foot', 'ToeBase': 'ball',
}
DIGITS = {'Index': 'index', 'Middle': 'middle', 'Ring': 'ring', 'Little': 'pinky', 'Thumb': 'thumb'}


def palm_rotation(position, wrist, middle, index, little):
    along = (position(middle) - position(wrist)).normalized()
    lateral = position(index) - position(little)
    normal = along.cross(lateral).normalized()
    return Matrix((along, normal.cross(along), normal)).transposed().to_quaternion()


class Cc0Motion:
    def __init__(self, soul, cc0, forearm_roll_share=1.0):
        self.soul = soul
        self.cc0 = cc0
        self.links = dict(CENTER)
        self.segments = {}
        self.forearm_roll_share = forearm_roll_share
        orientation = {}
        source_pos = lambda name: SOUL_TO_CC0 @ soul.data.bones[name].head_local
        target_pos = lambda name: cc0.data.bones[name].head_local
        for side in ('L', 'R'):
            prefix = f'J_Bip_{side}_'
            suffix = '_' + side.lower()
            self.links.update({prefix + joint: source + suffix for joint, source in LIMB.items()})
            wrist = prefix + 'Hand'
            handmarks = [wrist, *(prefix + digit + '1' for digit in ('Middle', 'Index', 'Little'))]
            for digit, source in DIGITS.items():
                for joint in range(1, 4):
                    self.links[f'{prefix}{digit}{joint}'] = f'{source}_{joint:02}{suffix}'
            target_palm = palm_rotation(target_pos, *handmarks)
            source_palm = palm_rotation(source_pos, *(self.links[name] for name in handmarks))
            palm_alignment = source_palm @ target_palm.inverted()
            orientation[wrist] = palm_alignment
            for digit in DIGITS:
                for joint in range(1, 4):
                    current = f'{prefix}{digit}{joint}'
                    if joint < 3:
                        child = f'{prefix}{digit}{joint + 1}'
                        before = target_pos(child) - target_pos(current)
                        after = source_pos(self.links[child]) - source_pos(self.links[current])
                        orientation[current] = (palm_alignment @ before).rotation_difference(after) @ palm_alignment
                    else:
                        orientation[current] = orientation[f'{prefix}{digit}2']

            for part, child in [('UpperArm', 'LowerArm'), ('LowerArm', 'Hand'), ('UpperLeg', 'LowerLeg'),
                                ('LowerLeg', 'Foot'), ('Foot', 'ToeBase')]:
                current, tip = prefix + part, prefix + child
                self.segments[current] = tip
                before = target_pos(tip) - target_pos(current)
                after = source_pos(self.links[tip]) - source_pos(self.links[current])
                orientation[current] = before.rotation_difference(after)

        self.world_alignment = {
            target: orientation.get(target, Quaternion()) @ cc0.data.bones[target].matrix_local.to_quaternion()
            for target in self.links
        }
        self.source_rest = {name: soul.data.bones[name].matrix_local.to_quaternion() for name in self.links.values()}
        self.travel_scale = (target_pos('J_Bip_C_Hips') - target_pos('Root')).z / (
            soul.data.bones['pelvis'].head_local - soul.data.bones['root'].head_local
        ).z
        for bone in cc0.pose.bones:
            bone.rotation_mode = 'QUATERNION'

    def apply(self):
        globals_by_name = {}
        for bone in self.cc0.pose.bones:
            local = Matrix.Identity(4)
            parent_args = {}
            if bone.parent:
                parent_args = {
                    'parent_matrix': globals_by_name[bone.parent.name],
                    'parent_matrix_local': bone.parent.bone.matrix_local,
                }
            rest = bone.bone.matrix_local
            if bone.name in self.links:
                source = self.soul.pose.bones[self.links[bone.name]]
                posed = source.matrix.to_quaternion()
                source_delta = posed @ self.source_rest[source.name].inverted()
                goal = SOUL_TO_CC0 @ source_delta @ SOUL_TO_CC0.inverted() @ self.world_alignment[bone.name]
                origin = bone.bone.convert_local_to_pose(local, rest, **parent_args)
                if bone.name.endswith('_LowerArm') and self.forearm_roll_share < 1:
                    child = self.cc0.data.bones[self.segments[bone.name]]
                    segment = rest.to_quaternion().inverted() @ (child.head_local - rest.translation)
                    base_rotation = origin.to_quaternion()
                    swing = (base_rotation @ segment).rotation_difference(goal @ segment)
                    # Preserve wrist direction and hand orientation. Share the
                    # pure axial twist across the original forearm and hand.
                    goal = (swing @ base_rotation).slerp(goal, self.forearm_roll_share)
                local = (origin.to_quaternion().inverted() @ goal).to_matrix().to_4x4()
                if bone.name in {'Root', 'J_Bip_C_Hips'}:
                    # Copy root and pelvis travel with the target's unit scale.
                    source_rest = source.bone.matrix_local
                    native_parent = {}
                    if source.parent:
                        native_parent = {'parent_matrix': source.parent.matrix,
                                         'parent_matrix_local': source.parent.bone.matrix_local}
                    baseline = source.bone.convert_local_to_pose(Matrix.Identity(4), source_rest, **native_parent)
                    travel = SOUL_TO_CC0 @ (source.head - baseline.translation)
                    local.translation = origin.to_quaternion().inverted() @ (travel * self.travel_scale)
            bone.matrix_basis = local
            globals_by_name[bone.name] = bone.bone.convert_local_to_pose(local, rest, **parent_args)

    def angle_errors(self):
        errors = {}
        for name, tip in self.segments.items():
            end = self.soul.pose.bones[self.links[tip]].head
            start = self.soul.pose.bones[self.links[name]].head
            expected = SOUL_TO_CC0 @ (end - start)
            cc0_axis = self.cc0.pose.bones[tip].head - self.cc0.pose.bones[name].head
            errors[name] = cc0_axis.angle(expected)
        return errors
