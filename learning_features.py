"""Safe, deliberately limited Python teaching simulator. Never uses exec/eval."""
import ast
import operator

BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow
}
CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge
}

class SimulationError(Exception):
    pass

def simulate_code(source):
    if len(source) > 3000:
        raise SimulationError("Please keep the code under 3,000 characters.")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SimulationError(f"Syntax error on line {exc.lineno}: {exc.msg}")
    env, output, steps = {}, [], []
    if len(tree.body) > 60:
        raise SimulationError("The simulator supports up to 60 top-level statements.")

    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise SimulationError(f"'{node.id}' has not been assigned a value.")
            return env[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            left, right = value(node.left), value(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise SimulationError("Large powers are not supported in the simulator.")
            return BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Not)):
            x = value(node.operand)
            return -x if isinstance(node.op, ast.USub) else (+x if isinstance(node.op, ast.UAdd) else not x)
        if isinstance(node, ast.BoolOp):
            vals = [value(v) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in CMP_OPS:
            return CMP_OPS[type(node.ops[0])](value(node.left), value(node.comparators[0]))
        if isinstance(node, ast.List):
            return [value(x) for x in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(value(x) for x in node.elts)
        raise SimulationError(f"Unsupported expression: {type(node).__name__}")

    def record(label):
        snapshot = ", ".join(f"{k} = {v!r}" for k, v in env.items()) or "No variables yet"
        steps.append({"line": label, "variables": snapshot, "output": "\n".join(map(str, output))})

    def run_statements(statements, depth=0):
        if depth > 5:
            raise SimulationError("Nested blocks are too deep for this teaching simulator.")
        for stmt in statements:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                env[stmt.targets[0].id] = value(stmt.value)
                record(f"Line {stmt.lineno}: assignment")
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value:
                env[stmt.target.id] = value(stmt.value)
                record(f"Line {stmt.lineno}: assignment")
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if isinstance(call.func, ast.Name) and call.func.id == "print":
                    if call.keywords:
                        raise SimulationError("print() keyword arguments are not supported.")
                    output.append(" ".join(str(value(arg)) for arg in call.args))
                    record(f"Line {stmt.lineno}: print")
                else:
                    raise SimulationError("Only print() function calls are supported.")
            elif isinstance(stmt, ast.If):
                condition = value(stmt.test)
                record(f"Line {stmt.lineno}: if condition = {condition}")
                run_statements(stmt.body if condition else stmt.orelse, depth + 1)
            elif isinstance(stmt, ast.For):
                if not isinstance(stmt.target, ast.Name) or not isinstance(stmt.iter, ast.Call):
                    raise SimulationError("Only for variable in range(...) loops are supported.")
                if not isinstance(stmt.iter.func, ast.Name) or stmt.iter.func.id != "range":
                    raise SimulationError("Only range() loops are supported.")
                args = [value(a) for a in stmt.iter.args]
                if not 1 <= len(args) <= 3 or not all(isinstance(x, int) for x in args):
                    raise SimulationError("range() needs one to three integer arguments.")
                sequence = range(*args)
                if len(sequence) > 20:
                    raise SimulationError("Loops are limited to 20 iterations.")
                for item in sequence:
                    env[stmt.target.id] = item
                    record(f"Line {stmt.lineno}: loop iteration")
                    run_statements(stmt.body, depth + 1)
            else:
                raise SimulationError(
                    f"Line {getattr(stmt, 'lineno', '?')}: {type(stmt).__name__} is not supported. "
                    "This simulator supports assignments, print(), if/else and simple range() loops."
                )
            if len(steps) > 150:
                raise SimulationError("The simulation reached its 150-step limit.")
    try:
        run_statements(tree.body)
    except SimulationError:
        raise
    except Exception as exc:
        raise SimulationError(f"Could not simulate this statement: {exc}")
    return {"steps": steps, "output": "\n".join(output), "variables": env}

PREDICT_QUESTIONS = [
    {"code": "x = 5\ny = 3\nprint(x + y)", "options": ["2", "8", "15", "53"], "answer": "8", "explanation": "The + operator adds 5 and 3."},
    {"code": "for i in range(3):\n    print(i)", "options": ["1 2 3", "0 1 2", "0 1 2 3", "3"], "answer": "0 1 2", "explanation": "range(3) produces 0, 1 and 2."},
    {"code": "n = 7\nif n % 2 == 0:\n    print('Even')\nelse:\n    print('Odd')", "options": ["Even", "Odd", "7", "Error"], "answer": "Odd", "explanation": "7 % 2 is 1, so the else block runs."},
    {"code": "word = 'Hi'\nprint(word * 2)", "options": ["Hi2", "Hi Hi", "HiHi", "Error"], "answer": "HiHi", "explanation": "Multiplying a string by 2 repeats it twice."},
    {"code": "total = 0\nfor n in range(1, 4):\n    total = total + n\nprint(total)", "options": ["3", "6", "10", "123"], "answer": "6", "explanation": "The loop adds 1 + 2 + 3."}
]
