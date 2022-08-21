# X軸を堺に選択点と対称になるように動かす
from collections import defaultdict
from math import sqrt

import bmesh
import bpy
import mathutils.kdtree
import numpy as np
from bpy.props import FloatProperty
from pulp import PULP_CBC_CMD, LpMaximize, LpProblem, LpVariable, lpSum, value

from .register_class import _get_cls


def matching(sels, lsts, th):
    """マッチングを求める

    1回目に最大マッチング問題を解き最大マッチング数(n)を求める
    2回目に移動距離を少なくするために最小重み最大マッチング問題を解く
    :param sels: 選択点のインデックスリスト
    :param lsts: 対称点の(インデックス, 距離)のリスト
    :param th: 移動範囲のしきい値
    :return: マッチングできた選択点のインデックスリスト、対称点のインデックスリスト
    """

    m = LpProblem(sense=LpMaximize)
    # 対称点の変数辞書、対称点から見た変数、1回目の目的関数、2回目の目的関数
    dcvar, dclnk, obj1s, obj2s = {}, defaultdict(list), [], []
    for sel, lst in zip(sels, lsts):
        ngh = []  # selと対応可能なマッチングの変数
        for tgt, dist in lst:
            v = LpVariable(f"v_{sel:04}_{tgt:04}", cat="Binary")
            dcvar[sel, tgt] = v
            dclnk[tgt].append(v)
            obj1s.append(v)
            obj2s.append(-((dist / th) ** 2) * v)
            ngh.append(v)
        m += lpSum(ngh) <= 1  # 選択点は1つまでマッチング可
    for vv in dclnk.values():
        m += lpSum(vv) <= 1  # 対称点は1つまでマッチング可

    # マッチングできた選択点のインデックスリスト、対称点のインデックスリスト
    ressel, restgt = [], []
    if not obj1s:
        return ressel, restgt
    solver = PULP_CBC_CMD(msg=False, gapRel=0.01, timeLimit=60)
    m.setObjective(lpSum(obj1s))
    m.solve(solver)  # 1回目
    if m.status != 1:
        return ressel, restgt
    n = round(value(m.objective))  # 最大マッチング数
    m += lpSum(obj1s) == n
    m.setObjective(lpSum(obj2s))
    m.solve(solver)  # 2回目
    for (sel, tgt), v in dcvar.items():
        if value(v) > 0.5:
            ressel.append(sel)
            restgt.append(tgt)
    return ressel, restgt


class CMI_OT_mirroring(bpy.types.Operator):
    """選択点と対になるように点を移動"""

    bl_idname = "object.mirroring"
    bl_label = "Mirroring"
    bl_description = "Mirroring the vertices."
    bl_options = {"REGISTER", "UNDO"}

    th: FloatProperty() = FloatProperty(default=0.05, precision=3)  # type: ignore

    def execute(self, context):
        # BMesh（bm）が使い回されないようにモードを切り替える
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="VERT")
        obj = bpy.context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        # 選択点のX座標に正が多いと1、そうでないと-1
        sgn = -1 if sum(v.co.x for v in bm.verts if v.select) < 0 else 1
        # 選択点のインデックス、選択点とマッチング可能な対称点のインデックスと距離、候補
        sels, lsts, cands = [], [], []
        for i, v in enumerate(bm.verts):
            match np.sign(np.round(v.co.x, 8)) * sgn:
                case 1:  # 選択点と同じ側
                    if v.select:
                        sels.append(i)
                        lsts.append([])
                case -1:  # 選択点と反対側
                    cands.append(i)
        kdt = mathutils.kdtree.KDTree(len(cands))  # KD-Tree
        for i in cands:
            kdt.insert(bm.verts[i].co, i)
        kdt.balance()
        mrx = mathutils.Vector((-1, 1, 1))
        for sel, lst in zip(sels, lsts):
            # X軸で対称な位置からself.th以内の点を探す
            for _, i, d in kdt.find_range(bm.verts[sel].co * mrx, self.th):
                lst.append((i, d))  # index, dist

        # マッチングを求める
        ressel, restgt = matching(sels, lsts, self.th)
        n = 0  # 対称点の中で、移動した点の個数
        for rs, rt in zip(ressel, restgt):
            tgt = bm.verts[rs].co.copy() * mrx
            if bm.verts[rt].co != tgt:
                bm.verts[rt].co = tgt
                n += 1
        self.report({"INFO"}, f"{n} moved")
        # 選択点の中で、マッチングがなかった点を再選択
        bpy.ops.mesh.select_all(action="DESELECT")
        for i in set(sels) - set(ressel):
            bm.verts[i].select_set(True)
        bm.free()
        del bm
        # 選択を反映するためにモードを切り替える
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}


class CMI_PT_bit(bpy.types.Panel):
    bl_label = "Mirroring"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Edit"
    bl_context = "mesh_edit"

    def draw(self, context):
        self.layout.prop(context.scene, "th", text="Th")
        text = CMI_OT_mirroring.bl_label
        prop = self.layout.operator(CMI_OT_mirroring.bl_idname, text=text)
        prop.th = context.scene.th


# __init__.pyで使用
ui_classes = _get_cls(__name__)
