from tree_sitter import Language, Parser
import tree_sitter_python

def test_parser():
    PY_LANGUAGE = Language(tree_sitter_python.language())
    parser = Parser(PY_LANGUAGE)

    code = b"""
    def foo():
        return "bar"
    """
    tree = parser.parse(code)
    root_node = tree.root_node
    print(f"Root type: {root_node.type}")
    print(f"Child count: {root_node.child_count}")

if __name__ == "__main__":
    test_parser()
