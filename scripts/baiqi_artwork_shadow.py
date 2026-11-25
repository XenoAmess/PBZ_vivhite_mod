"""Shadow flags shared by the packaged BaiQi meshes and their Unreal preview."""


CROWN_RELIEF_MATERIAL = 'BaiQi crown source color'
CROWN_RELIEF_PROPERTY = 'baiqi_crown_normal_strength'
CROWN_RELIEF_STRENGTH = .65


def set_baiqi_artwork_shadows(mesh, tools):
    for name in ('BaiQi bob front appearance', 'BaiQi side hair source color',
                 'BaiQi black gold headdress appearance', 'BaiQi round gold glasses appearance'):
        assert tools.set_section_cast_shadow(mesh, name, False) > 0, (mesh.get_path_name(), name)
    tools.set_section_cast_shadow(mesh, CROWN_RELIEF_MATERIAL, False)
