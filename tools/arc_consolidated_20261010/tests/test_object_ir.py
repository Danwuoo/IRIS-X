"""Portable schema/compiler checks; generated code is never host-executed."""
import ast
import copy
import json
import unittest

from tools.arc_consolidated_20261010 import arc_object_ir as ir
from tools.arc_consolidated_20261010.assets import load_legacy


class ObjectSchemaTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"steps": [{"op": "object_select_render", "partition": "foreground_cc8",
                     "background": "most_frequent", "selector": {"kind": "maxarea"},
                     "action": {"kind": "paint_mask", "color": 2}}]}

    def test_roundtrip_no_alias(self):
        checked = ir.parse_plan(json.dumps(self.plan))
        self.assertEqual(checked, self.plan)
        checked["steps"][0]["action"]["color"] = 4
        self.assertEqual(self.plan["steps"][0]["action"]["color"], 2)

    def test_all_literal_backgrounds_are_proposal_legal(self):
        for color in range(10):
            plan = copy.deepcopy(self.plan)
            plan["steps"][0]["background"] = color
            ir.compile_plan(plan)

    def test_strict_schema(self):
        bad = []
        for key, value in (("background", True), ("background", 1.0), ("background", 10),
                           ("partition", "import"), ("selector", {"kind":"minarea","color":0}),
                           ("action", {"kind":"paint_mask","color":False}),
                           ("action", {"kind":"paint_mask","color":2,"task_id":"x"})):
            plan = copy.deepcopy(self.plan)
            plan["steps"][0][key] = value
            bad.append(plan)
        bad += [{"steps":[]}, {"steps":self.plan["steps"]*4}, {"steps":self.plan["steps"],"task_id":"x"}]
        for plan in bad:
            with self.subTest(plan=plan), self.assertRaises(ir.PlanError):
                ir.validate_plan(plan)

    def test_strict_json_limits(self):
        values = ['{"steps":[],"steps":[]}', '{"steps":[{"op":"identity","op":"transpose"}]}',
                  '{"steps":[{"op":"recolor","source":NaN,"target":2}]}',
                  '{"steps":[{"op":"recolor","source":1.0,"target":2}]}',
                  '[['*1000, ' '*4097, '\ud800', '```json\n{}\n```']
        for value in values:
            with self.subTest(value=value[:40]), self.assertRaises(ir.PlanError):
                ir.parse_plan(value)

    def test_anchor_schema(self):
        plan = ir.unit_witnesses()[10]["plan"]
        ir.validate_plan(plan)
        plan["steps"][0]["anchor_selector"] = {"kind":"all"}
        with self.assertRaises(ir.PlanError):
            ir.validate_plan(plan)


class ObjectCompilerTests(unittest.TestCase):
    def test_pinned_integer_only_reducers_receive_integer_projections(self):
        # Inspect trusted templates as AST data only. The pinned VM rejects a
        # reducer over [row, column, color] pixels, even when host Python could
        # sort those lists. These expressions must project/encode integers.
        def integer_expression(node):
            if isinstance(node, ast.Constant):
                return type(node.value) is int
            if isinstance(node, ast.Name):
                return node.id in {'r0','r1','c0','c1','r','c'}
            if isinstance(node, ast.Subscript):
                return (isinstance(node.value,ast.Name) and node.value.id in {'v','box','ab'}
                        and isinstance(node.slice,ast.Constant) and type(node.slice.value) is int)
            if isinstance(node, ast.BinOp):
                return integer_expression(node.left) and integer_expression(node.right)
            return (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                    and node.func.id == 'len' and len(node.args) == 1)
        templates = (ir.BACKGROUND_SOURCE + ir.PARTITION_SOURCE + ir.SELECT_SOURCE +
                     ir.RENDER_SOURCE + ir.BBOX_SOURCE + ir.ANCHOR_SOURCE + ir.PANEL_SOURCE)
        reductions = [node for node in ast.walk(ast.parse(templates)) if isinstance(node,ast.Call)
                      and isinstance(node.func,ast.Name) and node.func.id in {'min','max','sum','sorted'}]
        self.assertTrue(reductions)
        for node in reductions:
            with self.subTest(expression=ast.unparse(node)):
                self.assertEqual(len(node.args),1)
                value = node.args[0]
                self.assertIsInstance(value,(ast.List,ast.ListComp))
                elements = value.elts if isinstance(value,ast.List) else [value.elt]
                self.assertTrue(all(integer_expression(element) for element in elements))
        for bad in ('v','obj','[v[0],v[1]]','(v[0],v[1])'):
            self.assertFalse(integer_expression(ast.parse(bad,mode='eval').body))

    def test_anchor_loop_helpers_do_not_recheck_whole_object_bank(self):
        tree = ast.parse(ir.ANCHOR_SOURCE)
        loop = next(node for node in ast.walk(tree) if isinstance(node,ast.For)
                    and isinstance(node.target,ast.Name) and node.target.id == 'obj')
        # oselect(objects,...) is the loop iterable and runs once. Inside its
        # body only the current object reaches a user-defined helper; passing
        # objects/g on each iteration would rewalk them at every VM call.
        self.assertEqual(ast.unparse(loop.iter),'oselect(objects, focus, color)')
        helpers = {'obackground','opartition','oselect','orender','obox','oanchor','opanels'}
        calls = [node for statement in loop.body for node in ast.walk(statement)
                 if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in helpers]
        self.assertEqual([ast.unparse(node) for node in calls],['obox(obj)'])
        selections = [node for node in ast.walk(tree) if isinstance(node,ast.Call)
                      and isinstance(node.func,ast.Name) and node.func.id == 'oselect']
        self.assertEqual(len(selections),2)

    def test_v2_rejects_removed_same_mask_relation_in_all_proposals(self):
        self.assertEqual(ir.IR_VERSION,'irisx/object-typed-ir-v2')
        self.assertEqual(ir.RELATIONS,('above','below','left','right','inside_bbox'))
        step = ir.unit_witnesses()[10]['plan']['steps'][0]
        for relation in ir.RELATIONS:
            ir.compile_plan({'steps':[{**step,'relation':relation}]})
        forbidden = {**step,'relation':'same_normalized_mask'}
        with self.assertRaises(ir.PlanError):
            ir.validate_plan({'steps':[forbidden]})
        with self.assertRaises(ir.PlanError):
            ir.parse_plan(json.dumps({'steps':[{'op':'identity'},forbidden,{'op':'transpose'}]}))
        self.assertNotIn('same_normalized_mask',ir.plan_contract())
        self.assertNotIn('sorted(',ir.ANCHOR_SOURCE)

    def test_legacy_source_unchanged(self):
        legacy = load_legacy("arc_typed_ir")
        for row in legacy.grammar_candidates():
            self.assertEqual(ir.compile_plan(row["plan"]), row["program"])

    def test_fixed_template_ast_and_caps(self):
        for control in ir.unit_witnesses():
            source = ir.compile_plan(control["plan"])
            tree = ast.parse(source)
            self.assertLessEqual(len(source.encode()), ir.MAX_SOURCE_BYTES)
            self.assertLessEqual(sum(1 for _ in ast.walk(tree)), ir.MAX_AST_NODES)
            self.assertLessEqual(len(tree.body), 8)
            self.assertTrue(all(isinstance(n, ast.FunctionDef) for n in tree.body))
            self.assertFalse(any(isinstance(n, (ast.Import,ast.ImportFrom,ast.Lambda)) for n in ast.walk(tree)))
            self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func,ast.Name)
                                 and n.func.id in ("exec","eval","compile","open") for n in ast.walk(tree)))

    def test_three_step_mixed_composition_within_caps(self):
        a = ir.unit_witnesses()[10]["plan"]["steps"][0]
        a = {**a, "background":"most_frequent"}
        plan = {"steps":[a, {"op":"largest_component_crop","background":0,"connectivity":8},
                         ir.unit_witnesses()[0]["plan"]["steps"][0]]}
        source = ir.compile_plan(plan)
        self.assertLessEqual(sum(1 for _ in ast.walk(ast.parse(source))), ir.MAX_AST_NODES)
        self.assertEqual(ir.production_ids(plan)[0], "length:3")

    def test_exact_finite_inventory_and_no_eager_execution(self):
        plans = ir.base_inventory()
        self.assertEqual(len(plans), 5965)
        self.assertEqual(len({ir.digest(p) for p in plans}), 5965)
        self.assertEqual(sum(p["steps"][0]["op"] == "object_select_render" and len(p['steps']) == 1 for p in plans), 1820)
        self.assertEqual(sum(p["steps"][0]["op"] == "object_select_render" and len(p['steps']) > 1 for p in plans), 280)
        self.assertEqual(sum(p["steps"][0]["op"] == "anchored_recolor" for p in plans), 1300)
        self.assertEqual(sum(p["steps"][0]["op"] == "equal_panels_boolean" for p in plans), 1280)
        self.assertEqual(sum(p["steps"][0]["op"] == "equal_panels_copy" for p in plans), 8)
        self.assertEqual({p["steps"][0]["background"] for p in plans[1277:] if 'background' in p['steps'][0]}, {0,"most_frequent"})
        manifest = ir.inventory_manifest()
        self.assertEqual(manifest["candidate_count"], 5965)
        self.assertEqual(manifest["primary_pool_ceiling"],5967)
        self.assertEqual(manifest["predecessor"]["removed_candidates"],260)
        self.assertFalse(any(step.get('relation') == 'same_normalized_mask' for plan in plans for step in plan['steps']))
        plans[0]["steps"][0]["op"] = "unsafe"
        self.assertNotEqual(ir.base_inventory()[0]["steps"][0]["op"], "unsafe")

    def test_all_inventory_templates_fit_caps(self):
        for plan in ir.base_inventory():
            with self.subTest(plan=plan):
                ir.compile_plan(plan)

    def test_smoke128_unique_family_cover(self):
        smoke = ir.smoke_inventory()
        self.assertEqual(len(smoke), 128)
        self.assertEqual(len({ir.digest(p) for p in smoke}), 128)
        self.assertTrue({ir.digest(p) for p in smoke} <= {ir.digest(p) for p in ir.base_inventory()})
        self.assertEqual({p['steps'][0]['op'] for p in smoke} & set(ir.NEW_OPS), set(ir.NEW_OPS))
        self.assertEqual(sum(p['steps'][0]['op'] == 'equal_panels_copy' for p in smoke), 8)

    def test_panels_schema_and_mixed_max_functions(self):
        panel = {"op":"equal_panels_boolean","axis":"cols","gap":1,"truth_table":15,
                 "foreground":7,"background":"most_frequent"}
        copy_panel = {"op":"equal_panels_copy","axis":"rows","gap":0,"direction":"second_to_first"}
        source = ir.compile_plan({"steps":[ir.unit_witnesses()[10]['plan']['steps'][0], panel, copy_panel]})
        self.assertEqual(len(ast.parse(source).body), 8)
        for key, value in [('gap',True),('truth_table',16),('truth_table',False),('axis','diagonal')]:
            with self.subTest(key=key), self.assertRaises(ir.PlanError):
                ir.validate_plan({'steps':[{**panel,key:value}]})


if __name__ == "__main__":
    unittest.main()
