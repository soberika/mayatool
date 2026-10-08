# -*- coding: utf-8 -*-
"""Start mcd. Dress Rig: drag this file into the Maya viewport.

The folder containing this file must also contain the folder mcd_dress_rig/.
Each start reloads the modules, so updated files take effect without
restarting Maya.
"""
import os
import sys


def _start(folder):
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import importlib
    import mcd_dress_rig
    from mcd_dress_rig import core, scene, pipeline, ui
    for module in (core, scene, pipeline, ui, mcd_dress_rig):
        importlib.reload(module)
    return mcd_dress_rig.show()


def onMayaDroppedPythonFile(*args):
    _start(os.path.dirname(os.path.abspath(__file__)))


if __name__ == '__main__':
    try:
        _start(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        raise RuntimeError('Bitte die Datei ins Viewport ziehen statt einfuegen.')
