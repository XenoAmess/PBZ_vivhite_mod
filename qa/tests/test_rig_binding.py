import unittest
from qa.rig_binding import binding_reasons
class BindingRegressionTests(unittest.TestCase):
    def fixture(self):
        return {'canonical_rig':'Armature','bones':264,'scene_armatures':['Armature'],'meshes':[{'object':'BaiQi_FemaleFoundation','armature_modifiers':[{'target':'Armature','enabled':True,'preserve_volume':False}]}]}
    def test_body_parent_without_skin_modifier_is_rejected(self):
        r=self.fixture();r['meshes'][0]['armature_modifiers']=[]
        self.assertTrue(binding_reasons(r))
    def test_different_rig_is_rejected(self):
        r=self.fixture();r['meshes'][0]['armature_modifiers'][0]['target']='Unlinked_duplicate'
        self.assertTrue(binding_reasons(r))
    def test_disabled_skin_modifier_is_rejected(self):
        r=self.fixture();r['meshes'][0]['armature_modifiers'][0]['enabled']=False
        self.assertTrue(binding_reasons(r))
    def test_valid_linear_binding_is_accepted(self):self.assertFalse(binding_reasons(self.fixture()))
