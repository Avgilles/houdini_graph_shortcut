import hou


def relink_null(node):
    if isinstance(node, hou.Node):
        if not node.userData("id_null"):
            return
        null_node = hou.nodeBySessionId(int(node.userData("id_null")))
        if null_node:
            node.setName("IN_" + null_node.name(), unique_name=True)
            node.parm("objpath1").set(node.relativePathTo(null_node))
            node.destroyUserData("id_null")
            
node = kwargs['node']
relink_null(node)
