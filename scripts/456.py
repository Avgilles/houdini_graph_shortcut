import hou  # noqa
from common.user_const import U_CONST


def assign_hotkeys(hotkeys_dict: dict):
    assigned = []
    if not hou.hotkeys.saveOverrides():
        print("ERROR: Couldn't save hotkey override file.")
        return ""
    if not hotkeys_dict:
        return ""
    for symbol, hotkey in hotkeys_dict.items():
        label = symbol.split(":")[-1]  # noqa: E231
        description = f"Tool for {label}"
        hou.hotkeys.addCommand(symbol, label, description)
        hou.hotkeys.addAssignment(symbol, hotkey)
        assigned.append(symbol)
    hou.hotkeys.saveOverrides()

    return assigned


if hou.isUIAvailable():
    assign_hotkeys(U_CONST.get("HOTKEYS_NODEGRAPH"))
