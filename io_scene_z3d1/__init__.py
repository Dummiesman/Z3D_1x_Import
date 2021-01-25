# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Created by Dummiesman, 2021
#
# ##### END LICENSE BLOCK #####

bl_info = {
    "name": "ZModeler v1.x Format",
    "author": "Dummiesman",
    "version": (0, 0, 1),
    "blender": (2, 90, 1),
    "location": "File > Import-Export",
    "description": "Import ZModeler v1.x files",
    "warning": "",
    "doc_url": "https://github.com/Dummiesman/Z3D_1x_Import/",
    "tracker_url": "https://github.com/Dummiesman/Z3D_1x_Import/",
    "support": 'COMMUNITY',
    "category": "Import-Export"}

import bpy
import textwrap 

from bpy.props import (
        BoolProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        CollectionProperty,
        )

from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )


class ImportZ3D1(bpy.types.Operator, ImportHelper):
    """Import from Z3D v1.x file format (.z3d)"""
    bl_idname = "import_scene.z3d1"
    bl_label = 'Import ZModeler v1.x File'
    bl_options = {'UNDO'}

    filename_ext = ".z3d"
    filter_glob: StringProperty(default="*.z3d", options={'HIDDEN'})

    def execute(self, context):
        from . import import_z3d1
        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "check_existing",
                                            ))

        return import_z3d1.load(self, context, **keywords)


# Add to a menu
def menu_func_import_z3d(self, context):
    self.layout.operator(ImportZ3D1.bl_idname, text="ZModeler v1.x (.z3d)")


# Register factories
def register():
    bpy.utils.register_class(ImportZ3D1)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_z3d)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_z3d)
    bpy.utils.unregister_class(ImportZ3D1)


if __name__ == "__main__":
    register()
