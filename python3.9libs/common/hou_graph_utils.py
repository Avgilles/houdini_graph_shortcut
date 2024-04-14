import hou
import canvaseventtypes
from common.user_const import U_CONST
from datetime import datetime
import nodegraphprefs as prefs
from contextlib import contextmanager


HOTKEY_CREATE_NULL = "X"
MOUSE_OFFSET = hou.Vector2(0.5, 0.2)


@contextmanager
def double_click_with_element(selected):
    if not hasattr(hou.session, "double_click_with_element"):
        time = datetime.now()
        hou.session.double_click_with_element = [time, selected]
        yield None
    else:
        second = datetime.now()
        get_time, get_selected = list(hou.session.double_click_with_element)
        diff = second - get_time
        mil_diff = diff.total_seconds() * 500
        if mil_diff < 400 and selected == get_selected:
            yield selected.item
        else:
            hou.session.double_click_with_element = [second, selected]
            yield None


def init_session(panes):
    # init user base pref
    if not hasattr(hou.session, "pref_dependency"):
        hou.session.pref_dependency = prefs.showDependencies(panes)
        hou.hscript("set -g PREF_DEPENDENCY=" + str(hou.session.pref_dependency) + "")
        hou.hscript("varchange PREF_DEPENDENCY")


# TODO : SET cursor pos on dependency link to swicth by double click
def jump_to_depency_link(item, panes):
    if isinstance(item, canvaseventtypes.NodeDependency) and len(item) > 1:
        nodes = hou.selectedNodes()
        if nodes and isinstance(item, tuple):
            for el in item:
                if el == nodes[0] or el is None:
                    continue
                panes.setCurrentNode(el)
                panes.homeToSelection()
        elif isinstance(item, tuple):
            if item.node:
                panes.setCurrentNode(item.node)
                panes.homeToSelection()


def show_depency_link(uievent):
    panes = uievent.editor
    if hasattr(hou.session, "pref_dependency"):
        if selected_on_mouse_drag(uievent):
            prefs.setShowDependencies(panes, 1)
        elif (
            uievent.eventtype in ["mousedown", "mouseup", "mouseexit", "mousedrag"]
            and uievent.mousestate.lmb
        ):
            set_link_node_pref(uievent, panes)


def selected_on_mouse_drag(uievent):
    if uievent.eventtype in ["mousemove"]:
        nodes = hou.selectedNodes()
        if nodes:
            has_allowed_node = True in [
                el.type().name() in U_CONST.get("DEPENDENCY_LINK_NODE_ALLOWED")
                for el in nodes
            ]
            if has_allowed_node:
                return True
    return False


def jump_to(n, panes):
    if n:
        merge_node_name = n.parm("objpath1").eval()
        merge_node = n.node(merge_node_name)
        if merge_node:
            panes.setCurrentNode(merge_node)
            panes.homeToSelection()


def set_link_node_pref(uievent, editor):
    if hasattr(uievent, "selected") and hasattr(uievent.selected, "item"):
        item = uievent.selected.item
        initial_pref = hou.session.pref_dependency
        if initial_pref == 0:
            if isinstance(item, canvaseventtypes.NodeDependency):
                return prefs.setShowDependencies(editor, 1)
            if isinstance(item, hou.Node):
                if item.type().name() in U_CONST.get("DEPENDENCY_LINK_NODE_ALLOWED"):
                    return prefs.setShowDependencies(editor, 1)
    return prefs.setShowDependencies(editor, hou.session.pref_dependency)


def follow_flags(parent, child):
    """check if the parent node is a tagged flag"""
    if parent.isDisplayFlagSet():
        child.setDisplayFlag(True)
    if parent.isRenderFlagSet():
        child.setRenderFlag(True)


def move_bellow_node(node, parent):
    """Move a node in the nodegraph under the current node"""
    if not parent.isNetwork():
        return
    origin = node.position()
    move = False
    for n_out in node.outputs():
        _, output_length = origin - n_out.position()
        if output_length < 2:
            move = True
    if move:
        all_nodes_in_parents = list(parent.children())
        if node in all_nodes_in_parents:
            all_nodes_in_parents.remove(node)
        for child in all_nodes_in_parents:
            pos = child.position()
            if pos[1] > origin[1]:
                continue
            pos[1] -= 1
            child.setPosition(pos)


# TODO : SET RELATIVE
def create_merge(node):
    if isinstance(node, hou.SopNode):
        merge_node = node.parent().createNode("object_merge")
        # merge_node.parm("objpath1").set(merge_node.relativePathTo(node))
        merge_node.parm("objpath1").set(node.path())
        node_name = node.name()
        if node_name.startswith("OUT"):
            node_name = node_name.replace("OUT_", "IN_")
        merge_node.setName(node_name, unique_name=True)
        merge_node.setPosition(node.position() + hou.Vector2(0, -2))
        return merge_node


def copy_merge(node):
    if isinstance(node, hou.SopNode):
        path = node.path()
        try:
            from PySide2 import QtWidgets

            cb = QtWidgets.QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(str(path), mode=cb.Clipboard)
        except Exception:
            print(path)
        with hou.undos.disabler():
            merge_node = create_merge(node)
            merge_node.setUserData("id_null", str(node.sessionId()))
            reset_comment_after_delay(node, "Copied in clipboard !")
            hou.copyNodesToClipboard((merge_node,))
            merge_node.destroy()


def create_null_between(name, node_input, pos, node_type, insert_between=False):
    """
    create null between connection

    :return: [node created]
    :rtype: [hou.node]
    """
    parent = node_input.parent()
    child = parent.createNode(name)
    child.setName("OUT_" + node_input.name(), unique_name=True)
    output_connections = node_input.outputConnections()
    if output_connections and insert_between:
        move_bellow_node(node_input, parent)
        for connection in output_connections:
            output_node = connection.outputNode()
            input_index = connection.inputIndex()
            output_node.setInput(input_index, child)
    child.setInput(0, node_input, 0)
    child.setPosition(pos)
    if node_type == "Sop":
        follow_flags(node_input, child)
    return child


# TODO : change name of the node by the input name
def create_merge_upward(node: hou.SopNode, pos: hou.Vector2):
    if isinstance(node, hou.SopNode):
        merge_node = node.parent().createNode("object_merge")
        merge_node.parm("objpath1").set(merge_node.relativePathTo(node))
        node_name = node.name()
        merge_node.setName(node_name, unique_name=True)
        merge_node.setPosition(pos)
        return merge_node


def create_speed_graph(c: hou.NodeConnection, pos=None):
    if not isinstance(c, hou.NodeConnection):
        return
    n_input = c.inputItem()
    n_input = c.inputNode()
    n_input_type = n_input.type().name()
    null_node = n_input
    input_pos = n_input.position()
    input_pos[1] -= 1
    if pos is None or not isinstance(pos, hou.Vector2):
        n_output = c.outputItem()
        pos = n_output.position()
        pos[1] += 1

    if n_input_type == "object_merge" and len(n_input.outputConnections()) <= 1:
        return n_input.setPosition(pos)
    if n_input_type not in ["null"]:
        node_type = n_input.type().category().name()
        null_node = create_null_between("null", n_input, input_pos, node_type, True)
    output = c.outputItem()
    in_index = c.inputIndex()
    merge_node = create_merge_upward(null_node, pos)
    output.setInput(in_index, merge_node)
    return null_node, merge_node


def create_null_alone(name, node_parent, pos):
    """
    create null

    :return: [node created]
    :rtype: [hou.node]
    """
    child = node_parent.createNode(name)
    child.setName("OUT_", unique_name=True)
    child.setPosition(pos)
    return child


def create_null_on_connection(item: hou.NodeConnection, name, pos):
    if item:
        node = item.inputNode()
        null_node = node.parent().createNode(name)
        output = item.outputNode()
        in_index = item.inputIndex()
        in_node = item.inputNode()
        output.setInput(in_index, null_node)
        null_node.setInput(0, in_node)
        null_node.setPosition(pos)


def create_merge_alone(name, node_parent, pos):
    """
    create merge

    :return: [node created]
    :rtype: [hou.node]
    """
    if isinstance(node_parent, hou.ObjNode):
        child = node_parent.createNode(name)
        child.setName("IN_", unique_name=True)
        child.setPosition(pos)
        return child


def create_speed_null(node_parent, pos, item):
    """Create null when a node is seleted

    :return: [list of node created]
    :rtype: [list]
    """
    insert_between = False
    selected = list(hou.selectedNodes())
    name_node = "null"
    if isinstance(item, hou.NodeConnection):
        return create_null_on_connection(item, name_node, pos)
    elif item:
        pos = item.position()
        pos[1] -= 1
        insert_between = True
        selected = [item]
    elif len(selected) == 0:
        return {create_null_alone(name_node, node_parent, pos)}
    nodes = sorted(selected, key=lambda node: node.position()[0])
    created_nodes = []
    allow_node = node_parent.children()
    for index, node in enumerate(nodes):
        if node not in allow_node:
            continue
        node_type = node.type().category().name()
        name_node = "null"
        if len(nodes) == 1:
            created_nodes.append(
                create_null_between(name_node, node, pos, node_type, insert_between)
            )
            return set(created_nodes)
        pos[0] += 2 if index else 0  # offset
        if item:
            pos = node.position()
            pos[1] -= 1
        created_nodes.append(
            create_null_between(name_node, node, pos, node_type, insert_between)
        )
        continue
    return set(created_nodes)


def set_pos_merge_node(node):
    if isinstance(node, hou.Node):
        output_nodes = node.outputs()
        node_type = node.type().name()
        parm_name = "objpath1" if node_type == "object_merge" else "merge_path"
        path_val = node.parm(parm_name).eval()
        for n in output_nodes:
            n_pos = n.position()
            n_pos -= hou.Vector2(0, -1)
            if len(output_nodes) == 1:
                return node.setPosition(n_pos)
            merge_node = create_merge_upward(n, n_pos)
            n.setInput(0, merge_node)
            merge_node.parm("objpath1").set(path_val)
        if len(output_nodes) >= 1:
            node.destroy()


def create_merge_from_input(node):
    if isinstance(node, hou.Node):
        n_pos = node.position()
        inputs = node.inputConnections()
        offset_beetween = 2.5
        max_dist = offset_beetween * len(inputs)

        if len(inputs) == 1:
            n_pos -= hou.Vector2(0, -1)
        else:
            n_pos -= hou.Vector2(max_dist / 2, -1)
        for key, i in enumerate(inputs):
            node = i.inputNode()
            if isinstance(node, hou.SopNode):
                if node.type().name() in ("object_merge"):
                    node.setPosition(n_pos)
                else:
                    create_speed_graph(i, n_pos)
                n_pos += hou.Vector2(offset_beetween, 0)


def reset_comment_after_delay(node, msg, time=3000):
    """reset message comment

    :param node: [node obj]
    :type node: [hou.node]
    :param msg: [msg to show]
    :type msg: [string]
    :param time: [time after reset], defaults to 5000
    :type time: int, optional
    """
    if hou.isUIAvailable():
        if not node:
            return
        if node.comment() == msg:
            return
        initial_comment = node.comment()
        node.setCachedUserData("init_msg", initial_comment)
        initial_comment = node.cachedUserData("init_msg")
        with hou.undos.disabler():
            # begin timer
            from PySide2.QtCore import (
                QTimer,
            )  # noqa  # pylint: disable=no-name-in-module

            timer = QTimer()

            def finish_delay():
                with hou.undos.disabler():
                    try:
                        node.setComment(initial_comment)
                        timer.stop()
                    except hou.ObjectWasDeleted:
                        return

            node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
            node.setComment(msg)
            timer.setSingleShot(True)
            timer.start(time)
            timer.timeout.connect(finish_delay)  # launch a the end of the timer


def jump_to_nodes(editor, to_nodes):
    """Jump network editor to node and frame it

    :param editor: the houdini network editor
    :type editor: hou.NetworkEditor
    :param nodes: the list of targeted nodes
    :type nodes: list of hou.Node
    """
    if not to_nodes:
        return
    editor.cd(to_nodes[0].parent().path())
    bounds = hou.BoundingRect()
    netbox = to_nodes[0].parent().createNetworkBox()
    editor.clearAllSelected()
    for node in to_nodes:
        netbox.addNode(node)
        node.setSelected(True)
    netbox.fitAroundContents()
    bounds.enlargeToContain(editor.itemRect(netbox))
    netbox.destroy()
    editor.setVisibleBounds(
        bounds, transition_time=0.0, max_scale=0.0, set_center_when_scale_rejected=False
    )
    editor.homeToSelection()


def hotkey_cmd(value):
    """Find the hotkey command for a given value.

    :param value: The value to search for in the dictionary.
    :type value: str

    :return: The hotkey command corresponding to the given value if found, otherwise None.
    :rtype: str or None
    """
    dictionary = U_CONST.get("HOTKEYS_NODEGRAPH")
    for key, val in dictionary.items():
        if val == value:
            return key
    return None


def nodegraph_hou_19(uievent, pending_actions):
    panes = uievent.editor
    init_session(panes)
    show_depency_link(uievent)

    if isinstance(uievent, canvaseventtypes.MouseEvent):
        selected = uievent.selected
        item = uievent.selected.item
        mouse_pos = panes.cursorPosition() - MOUSE_OFFSET
        if uievent.eventtype == "mousedown" and uievent.mousestate.mmb:
            if panes.isVolatileKeyDown(key=HOTKEY_CREATE_NULL):
                if isinstance(item, hou.NodeConnection):
                    with hou.undos.group("Create speed graph clean Shortcut"):
                        create_speed_graph(item)
                        return None, True
                if isinstance(item, hou.SopNode):
                    if item.type().name() in ("object_merge"):
                        with hou.undos.group("Place merge node"):
                            set_pos_merge_node(item)
                            return None, True
                    with hou.undos.group("Create speed graph merge"):
                        create_merge_from_input(item)
                        return None, True
                if panes.isVolatileHotkeyDown(hotkey_cmd("X")):
                    with hou.undos.group("Create object merge Shortcut"):
                        item = uievent.selected.item
                        parent_node = hou.node(panes.pwd().path())
                        print("hey")
                        create_merge_alone("object_merge", parent_node, mouse_pos)
                        return None, False
        if uievent.eventtype == "mousedown" and uievent.mousestate.lmb:
            if isinstance(item, canvaseventtypes.NodeDependency):
                with double_click_with_element(selected) as n:
                    jump_to_depency_link(n, panes)

            if isinstance(item, hou.Node):
                if item.type().name() == "null":
                    with double_click_with_element(selected) as n:
                        if selected.name == "node":
                            copy_merge(n)
                if item.type().name() == "object_merge":
                    with double_click_with_element(selected) as n:
                        if selected.name == "node":
                            jump_to(n, panes)

            if panes.isVolatileKeyDown(key=HOTKEY_CREATE_NULL):
                with hou.undos.group("Create Null Shortcut"):
                    item = uievent.selected.item
                    parent_node = hou.node(panes.pwd().path())
                    create_speed_null(parent_node, mouse_pos, item)
                    return None, False
    return None, False


def nodegraph_hou_20(uievent, pending_actions):
    panes = uievent.editor
    init_session(panes)
    show_depency_link(uievent)

    if isinstance(uievent, canvaseventtypes.MouseEvent):
        selected = uievent.selected
        item = uievent.selected.item
        mouse_pos = panes.cursorPosition() - MOUSE_OFFSET
        if uievent.eventtype == "mousedown" and uievent.mousestate.mmb:
            if panes.isVolatileHotkeyDown(hotkey_cmd("X")):
                if isinstance(item, hou.NodeConnection):
                    with hou.undos.group("Create speed graph clean Shortcut"):
                        create_speed_graph(item)
                        return None, True
                if isinstance(item, hou.SopNode):
                    if item.type().name() in ("object_merge"):
                        with hou.undos.group("Place merge node"):
                            set_pos_merge_node(item)
                            return None, True
                    with hou.undos.group("Create speed graph merge"):
                        create_merge_from_input(item)
                        return None, True
                if panes.isVolatileHotkeyDown(hotkey_cmd("X")):
                    with hou.undos.group("Create object merge Shortcut"):
                        item = uievent.selected.item
                        parent_node = hou.node(panes.pwd().path())
                        create_merge_alone("object_merge", parent_node, mouse_pos)
                        return None, False
        if uievent.eventtype == "mousedown" and uievent.mousestate.lmb:
            if isinstance(item, canvaseventtypes.NodeDependency):
                with double_click_with_element(selected) as n:
                    jump_to_depency_link(n, panes)

            if isinstance(item, hou.Node):
                if item.type().name() == "null":
                    with double_click_with_element(selected) as n:
                        print(n)
                        if selected.name == "node":
                            copy_merge(n)
                if item.type().name() == "object_merge":
                    with double_click_with_element(selected) as n:
                        if selected.name == "node":
                            jump_to(n, panes)

            if panes.isVolatileHotkeyDown(hotkey_cmd("X")):
                with hou.undos.group("Create Null Shortcut"):
                    item = uievent.selected.item
                    parent_node = hou.node(panes.pwd().path())
                    create_speed_null(parent_node, mouse_pos, item)
                    return None, False
    return None, False
