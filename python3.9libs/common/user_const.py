# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import json


def get_json_const():
    dir_name = os.path.dirname(__file__)
    file = os.path.join(dir_name, "user_default_pref.json")
    with open(file, "r", encoding="utf-8") as file:
        json_data = json.load(file)
        return json_data


U_CONST = get_json_const()
