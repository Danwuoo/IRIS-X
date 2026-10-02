"""Match the frozen Python 3.12 AST representation across reviewed runtimes."""
import ast


def portable_ast_dump(node):
    # Python 3.11 lacks empty type_params; Python 3.13+ hides empty fields
    # by default. The frozen Python 3.12 digest includes both.
    for item in ast.walk(node):
        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if getattr(item, 'type_params', []):
                raise RuntimeError('original class binding requires no type parameters')
            if 'type_params' not in item._fields:
                item._fields = (*item._fields, 'type_params')
                item.type_params = []
    try:
        return ast.dump(node, include_attributes=False, show_empty=True)
    except TypeError:
        return ast.dump(node, include_attributes=False)
