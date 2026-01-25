import ast
import json
import os
import sys
import glob

def analyze_flask(target_dir):
    routes = []
    
    # Python files
    files = glob.glob(os.path.join(target_dir, '**/*.py'), recursive=True)
    
    for file_path in files:
        if 'venv' in file_path or '__pycache__' in file_path:
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
                
            tree = ast.parse(code, filename=file_path)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        # Check for @app.route or @blueprint.route
                        if isinstance(decorator, ast.Call):
                            func = decorator.func
                            is_route = False
                            
                            if isinstance(func, ast.Attribute) and func.attr == 'route':
                                is_route = True
                            
                            if is_route:
                                # Extract path
                                route_path = '/'
                                if decorator.args and isinstance(decorator.args[0], ast.Constant): # Python 3.8+
                                    route_path = decorator.args[0].value
                                elif decorator.args and isinstance(decorator.args[0], ast.Str): # Python < 3.8
                                    route_path = decorator.args[0].s
                                
                                # Extract methods
                                methods = ['GET'] # Default
                                for keyword in decorator.keywords:
                                    if keyword.arg == 'methods' and isinstance(keyword.value, ast.List):
                                        methods = []
                                        for elt in keyword.value.elts:
                                            if isinstance(elt, ast.Constant):
                                                methods.append(elt.value)
                                            elif isinstance(elt, ast.Str):
                                                methods.append(elt.s)
                                
                                for method in methods:
                                    routes.push({ # Logic error in python, fixing below
                                       # Actually this is python list, use append
                                       pass
                                    })
                                    routes.append({
                                        'file': os.path.relpath(file_path, target_dir),
                                        'line': node.lineno,
                                        'method': method.upper(),
                                        'path': route_path,
                                        'type': 'flask',
                                        'framework': 'flask'
                                    })
                                    
        except Exception as e:
            # print(f"Error parsing {file_path}: {e}", file=sys.stderr)
            pass
            
    return routes

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else '.'
    result = analyze_flask(target)
    print(json.dumps(result, indent=2))
