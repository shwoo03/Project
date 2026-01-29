"""
Test suite for LSP (Language Server Protocol) integration.

Tests the LSP client module and API endpoints.
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.lsp_client import (
    # Types
    Position, Range, Location, TextDocumentIdentifier,
    SymbolKind, CompletionItemKind, MessageType,
    DocumentSymbol, SymbolInformation, Hover, CompletionItem, Diagnostic,
    
    # Config
    LanguageServerConfig, LANGUAGE_SERVERS,
    
    # Client
    LSPClient, LSPManager, JsonRpcTransport,
    
    # Functions
    get_lsp_manager, start_lsp_servers, stop_lsp_servers,
    goto_definition, find_references, get_hover_info,
    get_completions, get_symbols, search_symbols
)


class TestLSPTypes:
    """Test LSP protocol types."""
    
    def test_position_creation(self):
        """Test Position creation and serialization."""
        pos = Position(line=10, character=5)
        assert pos.line == 10
        assert pos.character == 5
        
        d = pos.to_dict()
        assert d == {"line": 10, "character": 5}
        
        pos2 = Position.from_dict(d)
        assert pos2.line == 10
        assert pos2.character == 5
    
    def test_range_creation(self):
        """Test Range creation and serialization."""
        r = Range(
            start=Position(line=5, character=0),
            end=Position(line=10, character=20)
        )
        
        d = r.to_dict()
        assert d['start']['line'] == 5
        assert d['end']['character'] == 20
        
        r2 = Range.from_dict(d)
        assert r2.start.line == 5
        assert r2.end.character == 20
    
    def test_location_creation(self):
        """Test Location creation and serialization."""
        loc = Location(
            uri="file:///test/file.py",
            range=Range(
                start=Position(0, 0),
                end=Position(10, 0)
            )
        )
        
        d = loc.to_dict()
        assert d['uri'] == "file:///test/file.py"
        assert d['range']['start']['line'] == 0
        
        loc2 = Location.from_dict(d)
        assert loc2.uri == "file:///test/file.py"
    
    def test_symbol_kind_enum(self):
        """Test SymbolKind enum values."""
        assert SymbolKind.CLASS.value == 5
        assert SymbolKind.FUNCTION.value == 12
        assert SymbolKind.VARIABLE.value == 13
        assert SymbolKind.METHOD.value == 6
    
    def test_completion_item_kind_enum(self):
        """Test CompletionItemKind enum values."""
        assert CompletionItemKind.TEXT.value == 1
        assert CompletionItemKind.METHOD.value == 2
        assert CompletionItemKind.FUNCTION.value == 3
        assert CompletionItemKind.CLASS.value == 7
    
    def test_document_symbol_from_dict(self):
        """Test DocumentSymbol deserialization."""
        data = {
            'name': 'TestClass',
            'kind': 5,  # CLASS
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 50, 'character': 0}
            },
            'selectionRange': {
                'start': {'line': 0, 'character': 6},
                'end': {'line': 0, 'character': 15}
            },
            'detail': 'class',
            'children': [
                {
                    'name': 'method1',
                    'kind': 6,  # METHOD
                    'range': {
                        'start': {'line': 10, 'character': 4},
                        'end': {'line': 20, 'character': 0}
                    },
                    'selectionRange': {
                        'start': {'line': 10, 'character': 8},
                        'end': {'line': 10, 'character': 15}
                    }
                }
            ]
        }
        
        symbol = DocumentSymbol.from_dict(data)
        assert symbol.name == 'TestClass'
        assert symbol.kind == SymbolKind.CLASS
        assert len(symbol.children) == 1
        assert symbol.children[0].name == 'method1'
        assert symbol.children[0].kind == SymbolKind.METHOD
    
    def test_hover_from_dict(self):
        """Test Hover deserialization."""
        data = {
            'contents': {'kind': 'markdown', 'value': '```python\ndef func(x: int) -> str\n```'},
            'range': {
                'start': {'line': 5, 'character': 0},
                'end': {'line': 5, 'character': 10}
            }
        }
        
        hover = Hover.from_dict(data)
        assert hover.contents['value'].startswith('```python')
        assert hover.range is not None
        assert hover.range.start.line == 5
    
    def test_completion_item_from_dict(self):
        """Test CompletionItem deserialization."""
        data = {
            'label': 'myFunction',
            'kind': 3,  # FUNCTION
            'detail': 'def myFunction(x: int) -> str',
            'documentation': 'Documentation for myFunction',
            'insertText': 'myFunction($1)'
        }
        
        item = CompletionItem.from_dict(data)
        assert item.label == 'myFunction'
        assert item.kind == CompletionItemKind.FUNCTION
        assert item.detail.startswith('def')
        assert '$1' in item.insert_text
    
    def test_diagnostic_from_dict(self):
        """Test Diagnostic deserialization."""
        data = {
            'range': {
                'start': {'line': 10, 'character': 5},
                'end': {'line': 10, 'character': 15}
            },
            'message': 'Undefined variable: x',
            'severity': 1,  # Error
            'code': 'E001',
            'source': 'pyright'
        }
        
        diag = Diagnostic.from_dict(data)
        assert diag.message == 'Undefined variable: x'
        assert diag.severity == 1
        assert diag.code == 'E001'
        assert diag.source == 'pyright'


class TestLanguageServerConfig:
    """Test language server configurations."""
    
    def test_python_config_exists(self):
        """Test Python language server config."""
        assert 'python' in LANGUAGE_SERVERS
        config = LANGUAGE_SERVERS['python']
        assert config.name == 'pyright'
        assert config.language_id == 'python'
        assert '.py' in config.file_extensions
        assert 'pyright-langserver' in config.command[0]
    
    def test_typescript_config_exists(self):
        """Test TypeScript language server config."""
        assert 'typescript' in LANGUAGE_SERVERS
        config = LANGUAGE_SERVERS['typescript']
        assert 'typescript-language-server' in config.command[0]
        assert '.ts' in config.file_extensions
        assert '.tsx' in config.file_extensions
    
    def test_javascript_config_exists(self):
        """Test JavaScript language server config."""
        assert 'javascript' in LANGUAGE_SERVERS
        config = LANGUAGE_SERVERS['javascript']
        assert '.js' in config.file_extensions
    
    def test_java_config_exists(self):
        """Test Java language server config."""
        assert 'java' in LANGUAGE_SERVERS
        config = LANGUAGE_SERVERS['java']
        assert config.name == 'jdtls'
        assert '.java' in config.file_extensions
    
    def test_go_config_exists(self):
        """Test Go language server config."""
        assert 'go' in LANGUAGE_SERVERS
        config = LANGUAGE_SERVERS['go']
        assert config.name == 'gopls'
        assert '.go' in config.file_extensions
    
    def test_rust_config_exists(self):
        """Test Rust language server config."""
        assert 'rust' in LANGUAGE_SERVERS
        config = LANGUAGE_SERVERS['rust']
        assert config.name == 'rust-analyzer'
        assert '.rs' in config.file_extensions
    
    def test_all_configs_have_required_fields(self):
        """Test all configs have required fields."""
        for lang, config in LANGUAGE_SERVERS.items():
            assert config.name, f"{lang} missing name"
            assert config.language_id, f"{lang} missing language_id"
            assert config.command, f"{lang} missing command"
            assert config.file_extensions, f"{lang} missing file_extensions"


class TestLSPClient:
    """Test LSP client functionality."""
    
    def test_path_to_uri_unix(self):
        """Test path to URI conversion for Unix paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LANGUAGE_SERVERS['python']
            client = LSPClient(config, tmpdir)
            
            # Test conversion
            path = os.path.join(tmpdir, 'test.py')
            uri = client._path_to_uri(path)
            
            assert uri.startswith('file://')
            assert 'test.py' in uri
    
    def test_uri_to_path(self):
        """Test URI to path conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LANGUAGE_SERVERS['python']
            client = LSPClient(config, tmpdir)
            
            # Convert to URI and back
            original_path = os.path.join(tmpdir, 'test.py')
            uri = client._path_to_uri(original_path)
            recovered_path = client._uri_to_path(uri)
            
            assert os.path.normpath(recovered_path) == os.path.normpath(original_path)
    
    def test_client_initialization_without_server(self):
        """Test client creation without starting server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LANGUAGE_SERVERS['python']
            client = LSPClient(config, tmpdir)
            
            assert client.workspace_root == tmpdir
            assert client.config == config
            assert not client._initialized
    
    @patch.object(LSPClient, '_command_exists', return_value=False)
    def test_start_fails_without_command(self, mock_cmd):
        """Test that start fails when command doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LANGUAGE_SERVERS['python']
            client = LSPClient(config, tmpdir)
            
            result = client.start()
            assert not result


class TestLSPManager:
    """Test LSP manager functionality."""
    
    def test_get_language_for_file(self):
        """Test language detection from file extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LSPManager(tmpdir)
            
            assert manager.get_language_for_file('test.py') == 'python'
            assert manager.get_language_for_file('test.ts') == 'typescript'
            assert manager.get_language_for_file('test.tsx') == 'typescript'
            assert manager.get_language_for_file('test.js') in ['javascript', 'typescript']
            assert manager.get_language_for_file('Test.java') == 'java'
            assert manager.get_language_for_file('main.go') == 'go'
            assert manager.get_language_for_file('lib.rs') == 'rust'
            assert manager.get_language_for_file('unknown.xyz') is None
    
    def test_manager_status_without_servers(self):
        """Test manager status when no servers started."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LSPManager(tmpdir)
            
            status = manager.get_status()
            assert status['workspace'] == tmpdir
            assert not status['started']
            assert len(status['servers']) == 0
            assert 'available_servers' in status
    
    def test_get_lsp_manager_singleton(self):
        """Test that get_lsp_manager returns same instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager1 = get_lsp_manager(tmpdir)
            manager2 = get_lsp_manager(tmpdir)
            
            assert manager1 is manager2
            
            # Cleanup
            stop_lsp_servers()
    
    def test_get_lsp_manager_different_workspace(self):
        """Test that different workspace creates new manager."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                manager1 = get_lsp_manager(tmpdir1)
                manager2 = get_lsp_manager(tmpdir2)
                
                # Different workspaces should create different managers
                assert manager1.workspace_root != manager2.workspace_root
                
                # Cleanup
                stop_lsp_servers()


class TestJsonRpcTransport:
    """Test JSON-RPC transport layer."""
    
    def test_message_format(self):
        """Test that messages are properly formatted."""
        # Create a mock process
        mock_process = Mock()
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        
        transport = JsonRpcTransport(mock_process)
        
        # Capture what gets written
        written_data = []
        mock_process.stdin.write = lambda data: written_data.append(data)
        mock_process.stdin.flush = Mock()
        
        # Send a notification
        transport.send_notification('test/method', {'key': 'value'})
        
        # Verify header format
        assert len(written_data) == 2
        header = written_data[0].decode('utf-8')
        assert 'Content-Length:' in header
        assert header.endswith('\r\n\r\n')
        
        # Verify content format
        import json
        content = json.loads(written_data[1].decode('utf-8'))
        assert content['jsonrpc'] == '2.0'
        assert content['method'] == 'test/method'
        assert content['params'] == {'key': 'value'}
        assert 'id' not in content  # Notifications don't have ID


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    def test_goto_definition_no_server(self):
        """Test goto_definition without server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('def hello():\n    pass\n')
            
            # Without starting server, should return empty list
            result = goto_definition(tmpdir, test_file, 0, 4)
            assert result == []
            
            stop_lsp_servers()
    
    def test_find_references_no_server(self):
        """Test find_references without server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('x = 1\nprint(x)\n')
            
            result = find_references(tmpdir, test_file, 0, 0)
            assert result == []
            
            stop_lsp_servers()
    
    def test_get_hover_info_no_server(self):
        """Test get_hover_info without server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('def func(x: int) -> str:\n    return str(x)\n')
            
            result = get_hover_info(tmpdir, test_file, 0, 4)
            assert result is None
            
            stop_lsp_servers()
    
    def test_get_completions_no_server(self):
        """Test get_completions without server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('import os\nos.\n')
            
            result = get_completions(tmpdir, test_file, 1, 3)
            assert result == []
            
            stop_lsp_servers()
    
    def test_get_symbols_no_server(self):
        """Test get_symbols without server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('class MyClass:\n    def method(self):\n        pass\n')
            
            result = get_symbols(tmpdir, test_file)
            assert result == []
            
            stop_lsp_servers()
    
    def test_search_symbols_no_server(self):
        """Test search_symbols without server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = search_symbols(tmpdir, 'MyClass')
            assert result == []
            
            stop_lsp_servers()


class TestIntegration:
    """Integration tests (requires language servers to be installed)."""
    
    @pytest.mark.skipif(
        not os.environ.get('RUN_LSP_INTEGRATION_TESTS'),
        reason="LSP integration tests disabled (set RUN_LSP_INTEGRATION_TESTS=1 to enable)"
    )
    def test_python_lsp_integration(self):
        """Test Python LSP integration (requires pyright)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file
            test_file = os.path.join(tmpdir, 'test_module.py')
            with open(test_file, 'w') as f:
                f.write('''
class Calculator:
    """A simple calculator class."""
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

def main():
    calc = Calculator()
    result = calc.add(1, 2)
    print(result)

if __name__ == "__main__":
    main()
''')
            
            # Start the server
            results = start_lsp_servers(tmpdir)
            
            if results.get('python'):
                import time
                time.sleep(2)  # Wait for initialization
                
                # Test goto definition
                locations = goto_definition(tmpdir, test_file, 14, 18)  # calc.add
                assert len(locations) > 0
                
                # Test hover
                hover = get_hover_info(tmpdir, test_file, 14, 18)
                assert hover is not None
                assert 'add' in hover.get('contents', '')
                
                # Test symbols
                symbols = get_symbols(tmpdir, test_file)
                assert len(symbols) > 0
                symbol_names = [s['name'] for s in symbols]
                assert 'Calculator' in symbol_names
            
            stop_lsp_servers()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
