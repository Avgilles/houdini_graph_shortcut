# -*- coding: utf-8 -*-
from __future__ import absolute_import
import hou
from common import hou_graph_utils as gu
# import importlib
"""
https://www.sidefx.com/docs/houdini/hom/network.html
https://www.sidefx.com/docs/houdini/hom/locations.html
"""


def eventgraph(uievent, pending_actions):
    return None, False


houdini_version = hou.applicationVersion()[0]
if houdini_version == 19:
    eventgraph = gu.nodegraph_hou_19  # noqa: F811
if houdini_version == 20:
    eventgraph = gu.nodegraph_hou_20


def createEventHandler(uievent, pending_actions):
    # importlib.reload(gu)
    try:
        eventgraph(uievent, pending_actions)
    except Exception:
        return None, False
    return None, False
