# -*- coding: utf-8 -*-
"""mcd. Dress Rig: base skinning for Second Life dresses on a skinned body (Maya 2024).

Start: drag mcd_dress_rig_start.py into the Maya viewport, or
    import mcd_dress_rig; mcd_dress_rig.show()
"""
VERSION = '0.5.14-M1'


def show():
    from . import ui
    return ui.DressRigWindow(VERSION)
