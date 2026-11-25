"""Shadow flags shared by the packaged BaiQi meshes and their Unreal preview."""


def set_baiqi_artwork_shadows(mesh, tools):
    for name in ('BaiQi bob front appearance', 'BaiQi side hair source color',
                 'BaiQi black gold headdress appearance', 'BaiQi round gold glasses appearance'):
        assert tools.set_section_cast_shadow(mesh, name, False) > 0, (mesh.get_path_name(), name)
