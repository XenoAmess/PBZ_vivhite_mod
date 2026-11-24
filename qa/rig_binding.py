"""Binding contract, independent of Blender and render colours."""
def binding_reasons(report):
    reasons=[];canonical=report.get('canonical_rig')
    if report.get('bones')!=264:reasons.append('native bone count is not 264')
    if report.get('scene_armatures')!=[canonical]:reasons.append('ambiguous scene armature')
    rows=report.get('meshes',[])
    if not rows:reasons.append('no mesh bindings inspected')
    for row in rows:
        mods=row.get('armature_modifiers',[])
        if len(mods)!=1:reasons.append(row['object']+': missing or multiple skin modifiers');continue
        mod=mods[0]
        if mod.get('target')!=canonical:reasons.append(row['object']+': different skin rig')
        if not mod.get('enabled'):reasons.append(row['object']+': skin modifier disabled')
        if mod.get('preserve_volume'):reasons.append(row['object']+': unsupported dual quaternion skin')
    return reasons
