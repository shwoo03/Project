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

    def parse(self, file_path: str, content: str, global_symbols: Dict[str, Dict] = None, symbol_table: Any = None) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        endpoints = []
        
        # If no global symbols provided, use local scan (backward compatibility)
        if global_symbols is None:
            global_symbols = self.scan_symbols(file_path, content)

        # Extract imports for this file
        file_imports = self.extract_imports(root_node, content)

        def get_node_text(node):
            return node.text.decode('utf-8')

        # ... (helpers omitted for brevity in diff, assume they exist) ...

        def traverse_clean(node, defined_funcs):
            return node.text.decode('utf-8')

        def extract_path_params(path_text: str) -> List[str]:
            # Flask: <id>, <int:id>
            # FastAPI: {id}
            flask_params = re.findall(r"<(?:[^:<>]+:)?([^<>]+)>", path_text)
            fastapi_params = re.findall(r"\{([^}]+)\}", path_text)
            return flask_params + fastapi_params

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
                     # Fallback for tree-sitter versions where field aliases might differ or not exist
                     if not name_node:
                         name_node = child.child(0)
                         
                     type_node = child.child_by_field_name('type')
                     p_name = get_node_text(name_node) if name_node else "unknown"
                     p_type = get_node_text(type_node) if type_node else "Any"
                     params.append(Parameter(name=p_name, type=p_type, source="unknown"))
                elif child.type == 'default_parameter':
                     name_node = child.child_by_field_name('name')
                     type_node = child.child_by_field_name('type')
                     
                     first_child = child.child(0)
                     if first_child.type == 'typed_parameter':
                         # Handle default with type hint: q: str = None
                         # first_child is typed_parameter
                         name_node = first_child.child_by_field_name('name')
                         if not name_node: name_node = first_child.child(0)
                         type_node = first_child.child_by_field_name('type')
                     elif not name_node:
                         # Handle simple default: q = None
                         name_node = first_child
                         
                     p_name = get_node_text(name_node) if name_node else "unknown"
                     p_type = get_node_text(type_node) if type_node else "Any"
                     params.append(Parameter(name=p_name, type=p_type, source="unknown"))
                
                elif child.type == 'typed_default_parameter':
                     # Handle typed default directly: q: str = None
                     name_node = child.child_by_field_name('name')
                     if not name_node: name_node = child.child(0)
                     
                     type_node = child.child_by_field_name('type')
                     # If type field missing, maybe child(2)? q : type = val
                     # Structure: identifier (0), : (1), type (2)
                     if not type_node and child.child_count > 2:
                         type_node = child.child(2)

                     p_name = get_node_text(name_node) if name_node else "unknown"
                     p_type = get_node_text(type_node) if type_node else "Any"
                     params.append(Parameter(name=p_name, type=p_type, source="unknown"))
            return params

        # Helper to find function calls inside a block
        def extract_calls(node, defined_funcs: Dict[str, Dict], file_imports: Dict[str, str] = None, symbol_table: Any = None) -> List[Dict]:
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

                    else:
                        # 2. General logic: Check Symbol Table -> Local Def -> Global Def
                        def_info = None
                        
                        # A. Symbol Table Resolution (Deep Analysis)
                        if symbol_table:
                             resolved = symbol_table.lookup(func_name, imports=file_imports)
                             if resolved:
                                 def_info = {
                                     "file_path": resolved.file_path,
                                     "start_line": resolved.line_number,
                                     "end_line": resolved.end_line_number,
                                     "filters": [], # TODO: Store filters in Symbol?
                                     "sanitization": []
                                 }
                        
                        # B. Local Definition
                        if not def_info and func_name in defined_funcs:
                             def_info = defined_funcs[func_name]
                        
                        # C. Global Dict Resolution (Fallback/Legacy)
                        if not def_info and func_name in global_symbols:
                             def_info = global_symbols[func_name]
                             
                        if def_info:
                            calls.append({
                                "name": func_name,
                                "def_info": def_info
                            })
            
            for child in node.children:
                calls.extend(extract_calls(child, defined_funcs, file_imports, symbol_table))
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
                    
                    # Pattern Match for Flask (@app.route) and FastAPI (@app.get, @router.post)
                    # Flask: @app.route("/path", methods=["POST"])
                    # FastAPI: @app.get("/path"), @router.post("/path")
                    
                    is_route = False
                    method = "GET" # Default
                    path = "/"
                    
                    if "@app.route" in decorator_text:
                        is_route = True
                        # Flask parsing logic (existing)
                        try:
                            parts = decorator_text.split('(')
                            if len(parts) > 1:
                                args = parts[1].split(')')[0].split(',')
                                path = args[0].strip().strip('"\'')
                                if ".post" in parts[0].lower() or "POST" in parts[1]: # Basic heuristic
                                     method = "POST"
                        except:
                            pass
                            
                    elif any(x in decorator_text for x in ["@app.get", "@app.post", "@app.put", "@app.delete", "@router.get", "@router.post", "@router.put", "@router.delete"]):
                        is_route = True
                        # FastAPI parsing logic
                        # Expected: @app.get("/users/{id}")
                        try:
                            # Extract method from decorator name
                            if ".get" in decorator_text: method = "GET"
                            elif ".post" in decorator_text: method = "POST"
                            elif ".put" in decorator_text: method = "PUT"
                            elif ".delete" in decorator_text: method = "DELETE"
                            
                            parts = decorator_text.split('(')
                            if len(parts) > 1:
                                # First arg is usually path
                                args = parts[1].split(')')[0].split(',')
                                path = args[0].strip().strip('"\'')
                        except:
                            pass

                    if is_route:

                        params = extract_params(definition) # Function args
                        path_params = extract_path_params(path)
                        if path_params:
                            for p in params:
                                if p.name in path_params:
                                    p.source = "path"
                                    
                        inputs = extract_inputs(definition) # Inside body
                        
                        # FastAPI/Modern Python: Treat non-path params as Inputs (Query/Body)
                        # Filter out 'self', 'cls', 'request'
                        if any(x in decorator_text for x in ["@app.get", "@app.post", "@app.put", "@app.delete", "@router."]):
                             for p in params:
                                 if p.source == "unknown" and p.name not in ["self", "cls", "request", "req"]:
                                     # Determine default source based on method usually, but 'query' is safe default for GET
                                     # For POST, complicated (Body vs Query). Let's default to 'input' type node.
                                     p_source = "query" if method == "GET" else "body" # Crude heuristic
                                     
                                     # Check if already in inputs (manually extracted?)
                                     if not any(i['name'] == p.name for i in inputs):
                                         inputs.append({
                                             "name": p.name,
                                             "source": p_source,
                                             "type": "UserInput"
                                         })

                        calls = extract_calls(definition, defined_funcs, file_imports, symbol_table) # Internal calls (using global defs)
                        filters = extract_sanitizers(definition)

                        sanitization = extract_sanitization_details(definition)
                        
                        sanitization = extract_sanitization_details(definition)
                        
                        # Extract SQL Queries
                        sql_nodes = self.extract_sql(definition, content)

                        children_nodes = []
                        children_nodes.extend(sql_nodes)
                        
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
                
                # Extract SQL Queries
                sql_nodes = self.extract_sql(node, content)

                children_nodes = []
                children_nodes.extend(sql_nodes)
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
                        file_path=file_path, 
                        line_number=node.start_point.row + 1,
                        
                        # Metadata for resolution
                        metadata={"definition": def_info},
                        
                        filters=def_info.get("filters", []),
                        sanitization=def_info.get("sanitization", []),
                        template_context=def_info.get("template_context", []),
                        template_usage=def_info.get("template_usage", []),
                        type="call"
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

        traverse_clean(root_node, global_symbols)
        
        # Post-process: If file has Routes (Roots), hide helper functions (Children) from top-level
        # This prevents helpers from appearing as siblings to Routes
        has_routes = any(ep.type == 'root' for ep in endpoints)
        if has_routes:
            endpoints = [ep for ep in endpoints if ep.type == 'root']
            
        return endpoints

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        def get_node_text(node):
            return node.text.decode('utf-8')

        defined_funcs = {} # Name -> {file_path, start_line, end_line}
        
        # We need sanitizer logic here too as it's part of def_info
        SANITIZER_FUNCTIONS = {
            "bleach.clean", "markupsafe.escape", "html.escape", "flask.escape",
            "werkzeug.utils.escape", "cgi.escape", "urllib.parse.quote", "urllib.parse.quote_plus",
        }
        SANITIZER_BASE_NAMES = {"escape", "sanitize"}
        
        def is_sanitizer(func_name: str) -> bool:
            lowered = func_name.lower()
            if lowered in SANITIZER_FUNCTIONS: return True
            base = lowered.split(".")[-1]
            return base in SANITIZER_BASE_NAMES

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
                                if child.is_named: args_list.append(get_node_text(child))
                        sanitizers.append({
                            "name": func_name,
                            "args": args_list,
                            "line": node.start_point.row + 1
                        })
            for child in node.children:
                sanitizers.extend(extract_sanitizers(child))
            return sanitizers

        # Helper: Extract variable bindings for parameter propagation analysis (lite version for symbol scan)
        def find_inputs_in_node(node): return [] # Placeholder if needed, but for symbol scan we might skip detailed graph build
        
        # Simplified sanitization details for symbol table (full detail is in parse)
        # Actually, let's keep it simple for scan: just Name/Loc. 
        # Detailed sanitization info is better extracted during full parse to avoid code duplication complexity?
        # But wait, 'def_info' in call node NEEDS this info. 
        # So we must extract it here or re-extract later. 
        # Let's duplicate minimal logic or just extract basic info here.
        
        def scan_funcs(n):
            if n.type == 'function_definition':
                name_node = n.child_by_field_name('name')
                if name_node: 
                    fn_name = get_node_text(name_node)
                    filters = extract_sanitizers(n)
                    
                    defined_funcs[fn_name] = {
                        "type": "function",
                        "file_path": file_path,
                        "start_line": n.start_point.row + 1,
                        "end_line": n.end_point.row + 1,
                        "filters": filters,
                        "sanitization": [],
                        "template_context": [],
                        "template_usage": []
                    }
            elif n.type == 'class_definition':
                name_node = n.child_by_field_name('name')
                if name_node:
                    class_name = get_node_text(name_node)
                    
                    # Extract inheritance
                    inherits = []
                    args_node = n.child_by_field_name('superclasses')
                    if args_node:
                        for child in args_node.children:
                            if child.is_named:
                                inherits.append(get_node_text(child))

                    defined_funcs[class_name] = {
                        "type": "class",
                        "file_path": file_path,
                        "start_line": n.start_point.row + 1,
                        "end_line": n.end_point.row + 1,
                        "inherits": inherits,
                        "filters": [],
                        "sanitization": [],
                        "template_context": [],
                        "template_usage": []
                    }
            for c in n.children: scan_funcs(c)
            
        scan_funcs(root_node)
        return defined_funcs

    def extract_sql(self, node, content: str) -> List[EndpointNodes]:
        sql_nodes = []
        
        # Manual traversal to find string nodes
        # avoids version issues with tree-sitter Query API
        nodes_to_visit = [node]
        seen_tables = set()

        while nodes_to_visit:
            curr = nodes_to_visit.pop()
            
            if curr.type == 'string' or curr.type == 'string_content':
                # Check text
                text = content[curr.start_byte:curr.end_byte]
                clean_text = text.strip("'\"")
                
                # Heuristic: Check for SQL keywords
                if re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE)\s", clean_text, re.IGNORECASE):
                    # Extract Table Name
                    table_match = re.search(r"(?:FROM|INTO|UPDATE)\s+([a-zA-Z0-9_]+)", clean_text, re.IGNORECASE)
                    if table_match:
                        table_name = table_match.group(1)
                        if table_name not in seen_tables:
                            seen_tables.add(table_name)
                            
                            sql_nodes.append(EndpointNodes(
                                id=f"sql-{table_name}-{curr.start_point[0]}",
                                path=f"Table: {table_name}",
                                method="SQL",
                                language="sql",
                                type="database",
                                file_path="database",
                                line_number=curr.start_point[0] + 1,
                                end_line_number=curr.end_point[0] + 1,
                                params=[],
                                children=[]
                            ))
            
            # Add children to stack
            # Optimization: don't traverse into other functions (optional, but extract_sql is called on func def)
            # But standard traversal is fine
            for child in curr.children:
                nodes_to_visit.append(child)
                
        return sql_nodes

    def extract_imports(self, node, content: str) -> Dict[str, str]:
        """
        Extract imports mapping: alias -> full_name
        e.g. from models import User -> {'User': 'models.User'}
        import utils -> {'utils': 'utils'}
        import utils as u -> {'u': 'utils'}
        """
        imports = {}
        
        stack = [node]
        while stack:
            curr = stack.pop()
            
            if curr.type == 'import_from_statement':
                # from module_name import name
                module_node = curr.child_by_field_name('module_name')
                if module_node:
                    module_name = content[module_node.start_byte:module_node.end_byte]
                    
                    # Iterate names
                    for child in curr.children:
                        if child.type == 'aliased_import':
                            # from x import y as z
                            name_node = child.child_by_field_name('name')
                            alias_node = child.child_by_field_name('alias')
                            if name_node and alias_node:
                                real_name = content[name_node.start_byte:name_node.end_byte]
                                alias = content[alias_node.start_byte:alias_node.end_byte]
                                imports[alias] = f"{module_name}.{real_name}"
                        elif child.type == 'dotted_name' and child != module_node:
                            # from x import y.z
                            name = content[child.start_byte:child.end_byte]
                            imports[name] = f"{module_name}.{name}"
                            pass
                        elif child.type == 'identifier' and child != module_node:
                            # from x import y
                            name = content[child.start_byte:child.end_byte]
                            imports[name] = f"{module_name}.{name}"
                            
            elif curr.type == 'import_statement':
                # import x, y as z
                for child in curr.children:
                    if child.type == 'dotted_name':
                        name = content[child.start_byte:child.end_byte]
                        imports[name] = name
                    elif child.type == 'aliased_import':
                        name_node = child.child_by_field_name('name')
                        alias_node = child.child_by_field_name('alias')
                        if name_node and alias_node:
                            real_name = content[name_node.start_byte:name_node.end_byte]
                            alias = content[alias_node.start_byte:alias_node.end_byte]
                            imports[alias] = real_name
            
            if curr.type not in ['function_definition', 'class_definition']:
                for c in curr.children:
                    stack.append(c)
                    
        return imports
