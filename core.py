import bpy
from bpy.props import FloatProperty

from .register_class import _get_cls


class CMI_OT_mirroring(bpy.types.Operator):
    """選択点と対になるように点を移動"""

    bl_idname = "object.mirroring"
    bl_label = "Mirroring"
    bl_description = "Mirroring the vertices."
    bl_options = {"REGISTER", "UNDO"}

    th: FloatProperty() = FloatProperty(default=0.005)  # type: ignore

    def execute(self, context):
        return {"FINISHED"}


class CMI_PT_bit(bpy.types.Panel):
    bl_label = "Mirroring"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Edit"
    bl_context = "editmode"

    def draw(self, context):
        self.layout.prop(context.scene, "limit", text="Th")
        text = CMI_OT_mirroring.bl_label
        prop = self.layout.operator(CMI_OT_mirroring.bl_idname, text=text)
        prop.limit = context.scene.limit


# __init__.pyで使用
ui_classes = _get_cls(__name__)
