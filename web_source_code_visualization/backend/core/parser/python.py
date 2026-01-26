from typing import List, Dict
from tree_sitter import Language, Parser
import tree_sitter_python
from .base import BaseParser
from models import EndpointNodes, Parameter

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
                    # Check if it references a known function
                    if func_name in defined_funcs:
                        calls.append({
                            "name": func_name,
                            "def_info": defined_funcs[func_name]
                        })
            
            for child in node.children:
                calls.extend(extract_calls(child, defined_funcs))
            return calls

        # Helper to find input usage
        def extract_inputs(node) -> List[Dict]:
            inputs = []
            # Look for:
            # - request.args.get("param") -> Query Param
            # - request.form.get("param") -> Form Data
            # - request.cookies.get("param") -> Cookie
            
            if node.type == 'call':
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

                    if source_type != "unknown":
                        # Extract arg
                        args = node.child_by_field_name('arguments')
                        if args:
                            first_arg = args.child(1) # child 0 is (
                            if first_arg and (first_arg.type == 'string' or first_arg.type == 'identifier'):
                                param_name = get_node_text(first_arg).strip('"\'')
                                inputs.append({
                                    "name": param_name,
                                    "source": source_type,
                                    "type": "UserInput"
                                })
            
            for child in node.children:
                inputs.extend(extract_inputs(child))
            return inputs

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
                        inputs = extract_inputs(definition) # Inside body
                        calls = extract_calls(definition, defined_funcs) # Internal calls
                        
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
                            end_line_number=node.end_point.row + 1
                        ))
                        should_recurse = False 

            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                func_name = get_node_text(name_node)
                
                params = extract_params(node)
                inputs = extract_inputs(node)
                calls = extract_calls(node, defined_funcs)
                
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
                    defined_funcs[fn_name] = {
                        "file_path": file_path,
                        "start_line": n.start_point.row + 1,
                        "end_line": n.end_point.row + 1
                    }
            for c in n.children: scan_funcs(c)
        scan_funcs(root_node)

        traverse_clean(root_node, defined_funcs)
        return endpoints
