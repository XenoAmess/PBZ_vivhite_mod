"""Review colours may change; silhouette masks must remain in both passes."""
class MaterialReview:
    def __init__(self,objects):
        self.objects=objects;self.original={o.name:list(o.data.materials) for o in objects};self.clay={}
        for materials in self.original.values():
            for material in materials:
                if material.name in self.clay:continue
                clone=material.copy();clone.name='QA alpha-preserved clay '+material.name
                if clone.use_nodes:
                    node=clone.node_tree.nodes.get('Principled BSDF')
                    if node:
                        for name in ['Base Color','Emission Color']:
                            if name not in node.inputs:continue
                            for link in list(node.inputs[name].links):clone.node_tree.links.remove(link)
                        node.inputs['Base Color'].default_value=(.36,.40,.44,1);node.inputs['Roughness'].default_value=.85
                        if 'Emission Strength' in node.inputs:node.inputs['Emission Strength'].default_value=0
                self.clay[material.name]=clone
    def apply(self,kind):
        for obj in self.objects:
            for i,mat in enumerate(self.original[obj.name]):obj.data.materials[i]=self.clay[mat.name] if kind=='clay' else mat
