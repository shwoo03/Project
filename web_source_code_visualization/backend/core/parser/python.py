from typing import List, Dict
from tree_sitter import Language, Parser
import tree_sitter_python
import os
import re
from .base import BaseParser
from models import EndpointNodes, Parameter

SANITIZER_FUNCTIONS = {
    "bleach.clean",
    "markupsafe.escape",
    "html.escape",
    "flask.escape",
    "werkzeug.utils.escape",
    "cgi.escape",
    "urllib.parse.quote",
    "urllib.parse.quote_plus",
}

SANITIZER_BASE_NAMES = {
    "escape",
    "sanitize",
}

class PythonParser(BaseParser):
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_python.language())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def parse(self, file_path: str, content: str) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        endpoints = []
        
        def get_node_text(node):
            return node.text.decode('utf-8')

        def extract_path_params(path_text: str) -> List[str]:
            return re.findall(r"<(?:[^:<>]+:)?([^<>]+)>", path_text)

        def extract_render_template_context(args_node) -> List[Dict]:
            context_vars = []
            if not args_node:
                return context_vars
            named_children = [child for child in args_node.children if child.is_named]
            start_index = 0
            if named_children and named_children[0].type == "string":
                start_index = 1

            for child in named_children[start_index:]:
                if child.type == "keyword_argument":
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        context_vars.append({"name": get_node_text(name_node)})
                elif child.type == "dictionary":
                    for pair in child.children:
                        if pair.type != "pair":
                            continue
                        key_node = pair.child_by_field_name('key')
                        if key_node:
                            key_text = get_node_text(key_node).strip('"\'')
                            context_vars.append({"name": key_text})
                elif child.type == "dictionary_splat":
                    context_vars.append({"name": get_node_text(child)})
                else:
                    text = get_node_text(child)
                    if "=" in text:
                        key = text.split("=", 1)[0].strip()
                        if key:
                            context_vars.append({"name": key})

            seen = set()
            unique_vars = []
            for item in context_vars:
                name = item.get("name")
                if not name or name in seen:
                    continue
                seen.add(name)
                unique_vars.append(item)
            return unique_vars

        def extract_template_usage(template_path: str) -> List[Dict]:
            usage = []
            try:
                with open(template_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                return usage

            for idx, line in enumerate(lines, start=1):
                for match in re.finditer(r"{{([^}]+)}}", line):
                    expr = match.group(1).strip()
                    expr = expr.split("|")[0].strip()
                    var_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expr)
                    if var_match:
                        usage.append({
                            "name": var_match.group(0),
                            "line": idx,
                            "snippet": line.strip()
                        })
            return usage

        def is_sanitizer(func_name: str) -> bool:
            lowered = func_name.lower()
            if lowered in SANITIZER_FUNCTIONS:
                return True
            base = lowered.split(".")[-1]
            return base in SANITIZER_BASE_NAMES

        def extract_params(func_node) -> List[Parameter]:
            params = []
            params_node = func_node.child_by_field_name('parameters')
            if not params_node:
                return params
                
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(Parameter(name=get_node_text(child), type="Any", source="unknown"))
                elif child.type == 'typed_parameter':
                     name_node = child.child_by_field_name('name')
                     type_node = child.child_by_field_name('type')
                     p_name = get_node_text(name_node) if name_node else "unknown"
                     p_type = get_node_text(type_node) if type_node else "Any"
                     params.append(Parameter(name=p_name, type=p_type, source="unknown"))
                elif child.type == 'default_parameter':
                     name_node = child.child_by_field_name('name')
                     type_node = child.child_by_field_name('type')
                     first_child = child.child(0)
                     if first_child.type == 'typed_parameter':
                         name_node = first_child.child_by_field_name('name')
                         type_node = first_child.child_by_field_name('type')
                     p_name = get_node_text(name_node) if name_node else "unknown"
                     p_type = get_node_text(type_node) if type_node else "Any"
                     params.append(Parameter(name=p_name, type=p_type, source="unknown"))
            return params

        # Helper to find function calls inside a block
        def extract_calls(node, defined_funcs: Dict[str, Dict]) -> List[Dict]:
            calls = []
            if node.type == 'call':
                func_node = node.child_by_field_name('function')
                if func_node:
                    func_name = get_node_text(func_node)
                    
                    # 1. Check for render_template("file.html")
                    if func_name == "render_template":
                        args = node.child_by_field_name('arguments')
                        if args:
                             first_arg = args.child(1) # ( arg )
                             if first_arg and first_arg.type == "string":
                                 template_name = get_node_text(first_arg).strip('"\'')
                                 # Try to find file
                                 # Assume templates is in sibling "templates" dir (Flask standard)
                                 # Current file_path: .../app.py -> .../templates/file.html
                                 base_dir = os.path.dirname(file_path)
                                 
                                 # Heuristic search for templates dir
                                 # 1. sibling 'templates'
                                 # 2. parent 'templates'
                                 
                                 candidates = [
                                     os.path.join(base_dir, "templates", template_name),
                                     os.path.join(os.path.dirname(base_dir), "templates", template_name)
                                 ]
                                 
                                 found_path = None
                                 for c in candidates:
                                     if os.path.exists(c):
                                         found_path = c
                                         break
                                 
                                 if found_path:
                                     context_vars = extract_render_template_context(args)
                                     template_usage = extract_template_usage(found_path)
                                     try:
                                         with open(found_path, "r", encoding="utf-8") as f:
                                             lines = f.readlines()
                                             end_line = len(lines)
                                     except:
                                         end_line = 0

                                     calls.append({
                                         "name": f"Template: {template_name}",
                                         "def_info": {
                                             "file_path": found_path,
                                             "start_line": 1,
                                             "end_line": end_line,
                                             "template_context": context_vars,
                                             "template_usage": template_usage
                                         }
                                     })

                    # 2. Check if it references a known function
                    elif func_name in defined_funcs:
                        calls.append({
                            "name": func_name,
                            "def_info": defined_funcs[func_name]
                        })
            
            for child in node.children:
                calls.extend(extract_calls(child, defined_funcs))
            return calls

        def get_input_from_call(node):
            if node.type != 'call':
                return None
            func_node = node.child_by_field_name('function')
            if func_node and func_node.type == 'attribute':
                text = get_node_text(func_node)
                source_type = "unknown"
                if "request.args.get" in text:
                    source_type = "GET"
                elif "request.form.get" in text:
                    source_type = "POST"
                elif "request.cookies.get" in text:
                    source_type = "COOKIE"
                elif "request.headers.get" in text:
                    source_type = "HEADER"
                elif "request.files.get" in text:
                    source_type = "FILE"
                elif "request.view_args.get" in text:
                    source_type = "PATH"
                elif "request.json.get" in text or "request.get_json" in text:
                    source_type = "BODY_JSON"
                elif "request.get_data" in text:
                    source_type = "BODY_RAW"
                if source_type != "unknown":
                    args = node.child_by_field_name('arguments')
                    if args:
                        first_arg = args.child(1)  # child 0 is (
                        if first_arg and (first_arg.type == 'string' or first_arg.type == 'identifier'):
                            param_name = get_node_text(first_arg).strip('"\'')
                            return {
                                "name": param_name,
                                "source": source_type,
                                "type": "UserInput"
                            }
                    if source_type == "BODY_JSON":
                        return {"name": "json", "source": source_type, "type": "UserInput"}
                    if source_type == "BODY_RAW":
                        return {"name": "data", "source": source_type, "type": "UserInput"}
            return None

        def get_input_from_subscript(node):
            if node.type != 'subscript':
                return None
            value_node = node.child_by_field_name('value')
            slice_node = node.child_by_field_name('slice')
            if not value_node or not slice_node:
                return None
            value_text = get_node_text(value_node)
            source_type = "unknown"
            if value_text == "request.args":
                source_type = "GET"
            elif value_text == "request.form":
                source_type = "POST"
            elif value_text == "request.cookies":
                source_type = "COOKIE"
            elif value_text == "request.headers":
                source_type = "HEADER"
            elif value_text == "request.files":
                source_type = "FILE"
            elif value_text == "request.view_args":
                source_type = "PATH"
            elif value_text == "request.json" or value_text.startswith("request.get_json"):
                source_type = "BODY_JSON"
            elif value_text == "request.data" or value_text.startswith("request.get_data"):
                source_type = "BODY_RAW"
            if source_type != "unknown":
                param_name = get_node_text(slice_node).strip('"\'')
                return {
                    "name": param_name,
                    "source": source_type,
                    "type": "UserInput"
                }
            return None

        def get_input_from_attribute(node):
            if node.type != 'attribute':
                return None
            text = get_node_text(node)
            if text == "request.json":
                return {"name": "json", "source": "BODY_JSON", "type": "UserInput"}
            if text == "request.data":
                return {"name": "data", "source": "BODY_RAW", "type": "UserInput"}
            return None
        def find_inputs_in_node(node) -> List[Dict]:
            inputs = []
            if node.type == 'call':
                input_info = get_input_from_call(node)
                if input_info:
                    inputs.append(input_info)
            elif node.type == 'subscript':
                input_info = get_input_from_subscript(node)
                if input_info:
                    inputs.append(input_info)
            elif node.type == 'attribute':
                input_info = get_input_from_attribute(node)
                if input_info:
                    inputs.append(input_info)
            for child in node.children:
                inputs.extend(find_inputs_in_node(child))
            return inputs
        # Helper to find input usage
        def extract_inputs(node) -> List[Dict]:
            inputs = []
            # Look for:
            # - request.args.get("param") -> Query Param
            # - request.form.get("param") -> Form Data
            # - request.cookies.get("param") -> Cookie
            # - request.headers.get("param") -> Header
            # - request.files.get("param") -> File
            # - request.view_args.get("param") -> Path Param
            # - request.json/get_json/request.data -> Body
            if node.type == 'call':
                input_info = get_input_from_call(node)
                if input_info:
                    inputs.append(input_info)
            elif node.type == 'subscript':
                input_info = get_input_from_subscript(node)
                if input_info:
                    inputs.append(input_info)
            elif node.type == 'attribute':
                input_info = get_input_from_attribute(node)
                if input_info:
                    inputs.append(input_info)
            for child in node.children:
                inputs.extend(extract_inputs(child))
            return inputs
        def collect_param_bindings(func_node) -> Dict[str, Dict]:
            bindings: Dict[str, Dict] = {}
            for param in extract_params(func_node):
                if param.name and param.name not in bindings:
                    bindings[param.name] = {
                        "name": param.name,
                        "source": "PARAM",
                        "type": "FunctionParam"
                    }
            return bindings
        def collect_input_bindings(node) -> Dict[str, Dict]:
            bindings: Dict[str, Dict] = {}
            def visit(n):
                if n.type == 'assignment':
                    left_node = n.child_by_field_name('left')
                    right_node = n.child_by_field_name('right')
                    if left_node and right_node and left_node.type == 'identifier':
                        inputs = find_inputs_in_node(right_node)
                        if inputs:
                            bindings[get_node_text(left_node)] = inputs[0]
                for child in n.children:
                    visit(child)
            visit(node)
            return bindings
        def extract_identifiers(node) -> List[str]:
            identifiers = []
            if node.type == 'identifier':
                identifiers.append(get_node_text(node))
            for child in node.children:
                identifiers.extend(extract_identifiers(child))
            return identifiers
        def extract_sanitization_details(func_node) -> List[Dict]:
            details = []
            seen = set()
            bindings = collect_input_bindings(func_node)
            param_bindings = collect_param_bindings(func_node)
            for key, value in param_bindings.items():
                if key not in bindings:
                    bindings[key] = value
            def visit(n):
                if n.type == 'call':
                    func_node_inner = n.child_by_field_name('function')
                    if func_node_inner:
                        func_name = get_node_text(func_node_inner)
                        if is_sanitizer(func_name):
                            args_node = n.child_by_field_name('arguments')
                            arg_texts = []
                            arg_nodes = []
                            if args_node:
                                for child in args_node.children:
                                    if child.is_named:
                                        arg_nodes.append(child)
                                        arg_texts.append(get_node_text(child))
                            line_no = n.start_point.row + 1
                            for arg in arg_nodes:
                                direct_inputs = find_inputs_in_node(arg)
                                if direct_inputs:
                                    for inp in direct_inputs:
                                        key = (inp["name"], inp["source"], func_name, line_no)
                                        if key in seen:
                                            continue
                                        seen.add(key)
                                        details.append({
                                            "input": inp["name"],
                                            "source": inp["source"],
                                            "sanitizer": func_name,
                                            "args": arg_texts,
                                            "line": line_no,
                                            "via": "direct"
                                        })
                                else:
                                    identifiers = extract_identifiers(arg)
                                    for ident in identifiers:
                                        if ident in bindings:
                                            inp = bindings[ident]
                                            key = (inp["name"], inp["source"], func_name, line_no, ident)
                                            if key in seen:
                                                continue
                                            seen.add(key)
                                            details.append({
                                                "input": inp["name"],
                                                "source": inp["source"],
                                                "sanitizer": func_name,
                                                "args": arg_texts,
                                                "line": line_no,
                                                "via": ident
                                            })
                for child in n.children:
                    visit(child)
            visit(func_node)
            return details

        def extract_sanitizers(node) -> List[Dict]:
            sanitizers = []
            if node.type == 'call':
                func_node = node.child_by_field_name('function')
                if func_node:
                    func_name = get_node_text(func_node)
                    if is_sanitizer(func_name):
                        args_list = []
                        args_node = node.child_by_field_name('arguments')
                        if args_node:
                            for child in args_node.children:
                                if child.is_named:
                                    args_list.append(get_node_text(child))
                        sanitizers.append({
                            "name": func_name,
                            "args": args_list,
                            "line": node.start_point.row + 1
                        })

            for child in node.children:
                sanitizers.extend(extract_sanitizers(child))
            return sanitizers

        def traverse_clean(node, defined_funcs: Dict[str, Dict]):
            should_recurse = True
            
            if node.type == 'decorated_definition':
                # ... (decorator logic remains same) ...
                decorator = node.child_by_field_name('decorator')
                definition = node.child_by_field_name('definition')
                
                if not decorator:
                    for child in node.children:
                        if child.type == 'decorator':
                            decorator = child
                            break
                if not definition:
                    for child in node.children:
                        if child.type == 'function_definition' or child.type == 'class_definition':
                            definition = child
                            break

                if decorator and definition:
                    # ... (route extraction logic) ...
                    decorator_text = get_node_text(decorator)
                    if "@app." in decorator_text or "route" in decorator_text:
                        # ...
                        method = "GET"
                        path = "/"
                        try:
                            parts = decorator_text.split('(')
                            if len(parts) > 1:
                                args = parts[1].split(')')[0].split(',')
                                path = args[0].strip().strip('"\'')
                                if ".post" in parts[0].lower() or "POST" in parts[1]:
                                    method = "POST"
                        except:
                            pass

                        params = extract_params(definition) # Function args
                        path_params = extract_path_params(path)
                        if path_params:
                            for p in params:
                                if p.name in path_params:
                                    p.source = "path"
                        inputs = extract_inputs(definition) # Inside body
                        calls = extract_calls(definition, defined_funcs) # Internal calls
                        filters = extract_sanitizers(definition)
                        sanitization = extract_sanitization_details(definition)
                        
                        children_nodes = []
                        
                        # Add Inputs as nodes
                        for inp in inputs:
                            children_nodes.append(EndpointNodes(
                                id=f"{file_path}:{node.start_point.row}:input:{inp['name']}",
                                path=inp['name'], 
                                method=inp['source'],
                                language="python",
                                file_path=file_path,
                                line_number=node.start_point.row + 1,
                                type="input"
                            ))
                            
                        # Add Calls as nodes
                        for call_info in calls:
                             def_info = call_info['def_info']
                             children_nodes.append(EndpointNodes(
                                id=f"{file_path}:{node.start_point.row}:call:{call_info['name']}",
                                path=call_info['name'],
                                method="CALL",
                                language="python",
                                # Use Definition Location
                                file_path=def_info['file_path'], 
                                line_number=def_info['start_line'],
                                end_line_number=def_info['end_line'],
                                filters=def_info.get("filters", []),
                                sanitization=def_info.get("sanitization", []),
                                template_context=def_info.get("template_context", []),
                                template_usage=def_info.get("template_usage", []),
                                type="child"
                            ))

                        endpoints.append(EndpointNodes(
                            id=f"{file_path}:{node.start_point.row}",
                            path=path,
                            method=method,
                            language="python",
                            file_path=file_path,
                            line_number=node.start_point.row + 1,
                            params=params, 
                            children=children_nodes,
                            type="root",
                            filters=filters,
                            sanitization=sanitization,
                            end_line_number=node.end_point.row + 1
                        ))
                        should_recurse = False 

            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                func_name = get_node_text(name_node)
                
                params = extract_params(node)
                inputs = extract_inputs(node)
                calls = extract_calls(node, defined_funcs)
                filters = extract_sanitizers(node)
                sanitization = extract_sanitization_details(node)
                
                children_nodes = []
                for inp in inputs:
                    children_nodes.append(EndpointNodes(
                        id=f"{file_path}:{node.start_point.row}:input:{inp['name']}",
                        path=inp['name'],
                        method=inp['source'],
                        language="python",
                        file_path=file_path,
                        line_number=node.start_point.row + 1,
                        type="input"
                    ))
                for call_info in calls:
                        def_info = call_info['def_info']
                        children_nodes.append(EndpointNodes(
                        id=f"{file_path}:{node.start_point.row}:call:{call_info['name']}",
                        path=call_info['name'],
                        method="CALL",
                        language="python",
                        # Use Definition Location
                        file_path=def_info['file_path'],
                        line_number=def_info['start_line'],
                        end_line_number=def_info['end_line'],
                        filters=def_info.get("filters", []),
                        sanitization=def_info.get("sanitization", []),
                        template_context=def_info.get("template_context", []),
                        template_usage=def_info.get("template_usage", []),
                        type="child"
                    ))

                endpoints.append(EndpointNodes(
                    id=f"{file_path}:{node.start_point.row}",
                    path=func_name,
                    method="FUNC",
                    language="python",
                    file_path=file_path,
                    line_number=node.start_point.row + 1,
                    params=params,
                    children=children_nodes,
                    type="child",
                    filters=filters,
                    sanitization=sanitization,
                    end_line_number=node.end_point.row + 1
                ))
            
            if should_recurse:
                for child in node.children:
                    traverse_clean(child, defined_funcs)

        # 1. Pre-scan for defined function names and locations
        defined_funcs = {} # Name -> {file_path, start_line, end_line}
        def scan_funcs(n):
            if n.type == 'function_definition':
                name_node = n.child_by_field_name('name')
                if name_node: 
                    fn_name = get_node_text(name_node)
                    filters = extract_sanitizers(n)
                    sanitization = extract_sanitization_details(n)
                    defined_funcs[fn_name] = {
                        "file_path": file_path,
                        "start_line": n.start_point.row + 1,
                        "end_line": n.end_point.row + 1,
                        "filters": filters,
                        "sanitization": sanitization
                    }
            for c in n.children: scan_funcs(c)
        scan_funcs(root_node)

        traverse_clean(root_node, defined_funcs)
        return endpoints





