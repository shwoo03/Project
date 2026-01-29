"""
Language Server Protocol (LSP) Client Module

Provides LSP integration for enhanced code analysis:
- Accurate type information from language servers
- Go-to-definition with high accuracy
- IDE-level symbol resolution
- Hover information (documentation, signatures)
- Find references across project

Supported Language Servers:
- Python: Pylance, Pyright, python-lsp-server
- TypeScript/JavaScript: typescript-language-server
- Java: Eclipse JDT Language Server
- Go: gopls
- Rust: rust-analyzer
"""

import os
import sys
import json
import subprocess
import threading
import queue
import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import socket

logger = logging.getLogger(__name__)


# =============================================================================
# LSP Protocol Types
# =============================================================================

class MessageType(int, Enum):
    """LSP MessageType."""
    ERROR = 1
    WARNING = 2
    INFO = 3
    LOG = 4


class SymbolKind(int, Enum):
    """LSP SymbolKind."""
    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOLEAN = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUM_MEMBER = 22
    STRUCT = 23
    EVENT = 24
    OPERATOR = 25
    TYPE_PARAMETER = 26


class CompletionItemKind(int, Enum):
    """LSP CompletionItemKind."""
    TEXT = 1
    METHOD = 2
    FUNCTION = 3
    CONSTRUCTOR = 4
    FIELD = 5
    VARIABLE = 6
    CLASS = 7
    INTERFACE = 8
    MODULE = 9
    PROPERTY = 10
    UNIT = 11
    VALUE = 12
    ENUM = 13
    KEYWORD = 14
    SNIPPET = 15
    COLOR = 16
    FILE = 17
    REFERENCE = 18
    FOLDER = 19
    ENUM_MEMBER = 20
    CONSTANT = 21
    STRUCT = 22
    EVENT = 23
    OPERATOR = 24
    TYPE_PARAMETER = 25


@dataclass
class Position:
    """LSP Position (0-indexed)."""
    line: int
    character: int
    
    def to_dict(self) -> Dict:
        return {"line": self.line, "character": self.character}
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Position':
        return cls(line=d['line'], character=d['character'])


@dataclass
class Range:
    """LSP Range."""
    start: Position
    end: Position
    
    def to_dict(self) -> Dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Range':
        return cls(
            start=Position.from_dict(d['start']),
            end=Position.from_dict(d['end'])
        )


@dataclass
class Location:
    """LSP Location."""
    uri: str
    range: Range
    
    def to_dict(self) -> Dict:
        return {"uri": self.uri, "range": self.range.to_dict()}
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Location':
        return cls(
            uri=d['uri'],
            range=Range.from_dict(d['range'])
        )


@dataclass
class TextDocumentIdentifier:
    """LSP TextDocumentIdentifier."""
    uri: str
    
    def to_dict(self) -> Dict:
        return {"uri": self.uri}


@dataclass
class TextDocumentPositionParams:
    """LSP TextDocumentPositionParams."""
    text_document: TextDocumentIdentifier
    position: Position
    
    def to_dict(self) -> Dict:
        return {
            "textDocument": self.text_document.to_dict(),
            "position": self.position.to_dict()
        }


@dataclass
class SymbolInformation:
    """LSP SymbolInformation."""
    name: str
    kind: SymbolKind
    location: Location
    container_name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'SymbolInformation':
        return cls(
            name=d['name'],
            kind=SymbolKind(d['kind']),
            location=Location.from_dict(d['location']),
            container_name=d.get('containerName')
        )


@dataclass
class DocumentSymbol:
    """LSP DocumentSymbol."""
    name: str
    kind: SymbolKind
    range: Range
    selection_range: Range
    detail: Optional[str] = None
    children: List['DocumentSymbol'] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'DocumentSymbol':
        children = [cls.from_dict(c) for c in d.get('children', [])]
        return cls(
            name=d['name'],
            kind=SymbolKind(d['kind']),
            range=Range.from_dict(d['range']),
            selection_range=Range.from_dict(d['selectionRange']),
            detail=d.get('detail'),
            children=children
        )


@dataclass
class Hover:
    """LSP Hover result."""
    contents: Any  # MarkedString | MarkedString[] | MarkupContent
    range: Optional[Range] = None
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Hover':
        return cls(
            contents=d.get('contents'),
            range=Range.from_dict(d['range']) if d.get('range') else None
        )


@dataclass
class CompletionItem:
    """LSP CompletionItem."""
    label: str
    kind: Optional[CompletionItemKind] = None
    detail: Optional[str] = None
    documentation: Optional[Any] = None
    insert_text: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'CompletionItem':
        return cls(
            label=d['label'],
            kind=CompletionItemKind(d['kind']) if d.get('kind') else None,
            detail=d.get('detail'),
            documentation=d.get('documentation'),
            insert_text=d.get('insertText')
        )


@dataclass
class Diagnostic:
    """LSP Diagnostic."""
    range: Range
    message: str
    severity: Optional[int] = None  # 1=Error, 2=Warning, 3=Info, 4=Hint
    code: Optional[Any] = None
    source: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Diagnostic':
        return cls(
            range=Range.from_dict(d['range']),
            message=d['message'],
            severity=d.get('severity'),
            code=d.get('code'),
            source=d.get('source')
        )


# =============================================================================
# LSP Language Server Configuration
# =============================================================================

@dataclass
class LanguageServerConfig:
    """Configuration for a language server."""
    name: str
    language_id: str
    command: List[str]
    file_extensions: List[str]
    initialization_options: Dict = field(default_factory=dict)
    settings: Dict = field(default_factory=dict)
    root_uri_markers: List[str] = field(default_factory=list)


# Default language server configurations
LANGUAGE_SERVERS: Dict[str, LanguageServerConfig] = {
    'python': LanguageServerConfig(
        name='pyright',
        language_id='python',
        command=['pyright-langserver', '--stdio'],
        file_extensions=['.py', '.pyi'],
        initialization_options={},
        settings={
            'python': {
                'analysis': {
                    'autoSearchPaths': True,
                    'useLibraryCodeForTypes': True,
                    'diagnosticMode': 'workspace',
                }
            }
        },
        root_uri_markers=['pyproject.toml', 'setup.py', 'requirements.txt', '.git']
    ),
    'typescript': LanguageServerConfig(
        name='typescript-language-server',
        language_id='typescript',
        command=['typescript-language-server', '--stdio'],
        file_extensions=['.ts', '.tsx', '.js', '.jsx'],
        initialization_options={
            'preferences': {
                'includeInlayParameterNameHints': 'all',
                'includeInlayPropertyDeclarationTypeHints': True,
                'includeInlayFunctionLikeReturnTypeHints': True,
            }
        },
        settings={},
        root_uri_markers=['package.json', 'tsconfig.json', '.git']
    ),
    'javascript': LanguageServerConfig(
        name='typescript-language-server',
        language_id='javascript',
        command=['typescript-language-server', '--stdio'],
        file_extensions=['.js', '.jsx', '.mjs', '.cjs'],
        initialization_options={},
        settings={},
        root_uri_markers=['package.json', '.git']
    ),
    'java': LanguageServerConfig(
        name='jdtls',
        language_id='java',
        command=['jdtls'],  # Eclipse JDT Language Server
        file_extensions=['.java'],
        initialization_options={},
        settings={},
        root_uri_markers=['pom.xml', 'build.gradle', '.git']
    ),
    'go': LanguageServerConfig(
        name='gopls',
        language_id='go',
        command=['gopls', 'serve'],
        file_extensions=['.go'],
        initialization_options={},
        settings={
            'gopls': {
                'staticcheck': True,
                'analyses': {
                    'unusedparams': True,
                    'shadow': True,
                }
            }
        },
        root_uri_markers=['go.mod', 'go.sum', '.git']
    ),
    'rust': LanguageServerConfig(
        name='rust-analyzer',
        language_id='rust',
        command=['rust-analyzer'],
        file_extensions=['.rs'],
        initialization_options={},
        settings={},
        root_uri_markers=['Cargo.toml', '.git']
    ),
}


# =============================================================================
# JSON-RPC Transport
# =============================================================================

class JsonRpcTransport:
    """JSON-RPC transport for LSP communication."""
    
    def __init__(self, process: subprocess.Popen):
        self.process = process
        self.stdin = process.stdin
        self.stdout = process.stdout
        self._request_id = 0
        self._pending_requests: Dict[int, queue.Queue] = {}
        self._notification_handlers: Dict[str, Callable] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
    
    def start(self):
        """Start the reader thread."""
        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
    
    def stop(self):
        """Stop the transport."""
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=2.0)
    
    def _read_loop(self):
        """Read messages from stdout."""
        while self._running:
            try:
                message = self._read_message()
                if message:
                    self._handle_message(message)
            except Exception as e:
                if self._running:
                    logger.error(f"Error reading message: {e}")
                break
    
    def _read_message(self) -> Optional[Dict]:
        """Read a single LSP message."""
        # Read headers
        headers = {}
        while True:
            line = self.stdout.readline()
            if not line:
                return None
            
            line = line.decode('utf-8').strip()
            if not line:
                break
            
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
        # Read content
        content_length = int(headers.get('content-length', 0))
        if content_length == 0:
            return None
        
        content = self.stdout.read(content_length)
        return json.loads(content.decode('utf-8'))
    
    def _handle_message(self, message: Dict):
        """Handle an incoming message."""
        if 'id' in message and 'result' in message or 'error' in message:
            # Response
            request_id = message['id']
            with self._lock:
                if request_id in self._pending_requests:
                    self._pending_requests[request_id].put(message)
        elif 'method' in message and 'id' not in message:
            # Notification
            method = message['method']
            if method in self._notification_handlers:
                try:
                    self._notification_handlers[method](message.get('params', {}))
                except Exception as e:
                    logger.error(f"Error handling notification {method}: {e}")
    
    def send_request(self, method: str, params: Dict = None, timeout: float = 30.0) -> Optional[Any]:
        """Send a request and wait for response."""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            response_queue = queue.Queue()
            self._pending_requests[request_id] = response_queue
        
        message = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
        }
        if params is not None:
            message['params'] = params
        
        self._send_message(message)
        
        try:
            response = response_queue.get(timeout=timeout)
            if 'error' in response:
                logger.error(f"LSP error: {response['error']}")
                return None
            return response.get('result')
        except queue.Empty:
            logger.warning(f"Request {method} timed out")
            return None
        finally:
            with self._lock:
                self._pending_requests.pop(request_id, None)
    
    def send_notification(self, method: str, params: Dict = None):
        """Send a notification (no response expected)."""
        message = {
            'jsonrpc': '2.0',
            'method': method,
        }
        if params is not None:
            message['params'] = params
        
        self._send_message(message)
    
    def _send_message(self, message: Dict):
        """Send a message to the server."""
        content = json.dumps(message)
        content_bytes = content.encode('utf-8')
        
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        
        self.stdin.write(header.encode('utf-8'))
        self.stdin.write(content_bytes)
        self.stdin.flush()
    
    def on_notification(self, method: str, handler: Callable):
        """Register a notification handler."""
        self._notification_handlers[method] = handler


# =============================================================================
# LSP Client
# =============================================================================

class LSPClient:
    """
    Language Server Protocol Client.
    
    Manages connection to a language server and provides
    high-level API for code intelligence features.
    """
    
    def __init__(self, config: LanguageServerConfig, workspace_root: str):
        self.config = config
        self.workspace_root = os.path.abspath(workspace_root)
        self.workspace_uri = self._path_to_uri(self.workspace_root)
        
        self.process: Optional[subprocess.Popen] = None
        self.transport: Optional[JsonRpcTransport] = None
        self._initialized = False
        self._open_documents: Dict[str, int] = {}  # uri -> version
        self._diagnostics: Dict[str, List[Diagnostic]] = {}
    
    def _path_to_uri(self, path: str) -> str:
        """Convert a file path to URI."""
        path = os.path.abspath(path)
        if sys.platform == 'win32':
            path = '/' + path.replace('\\', '/')
        return f"file://{path}"
    
    def _uri_to_path(self, uri: str) -> str:
        """Convert a URI to file path."""
        if uri.startswith('file://'):
            path = uri[7:]
            if sys.platform == 'win32' and path.startswith('/'):
                path = path[1:]
            return path.replace('/', os.sep)
        return uri
    
    def start(self) -> bool:
        """Start the language server."""
        try:
            # Check if command exists
            cmd = self.config.command[0]
            if not self._command_exists(cmd):
                logger.warning(f"Language server command not found: {cmd}")
                return False
            
            # Start the process
            self.process = subprocess.Popen(
                self.config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace_root
            )
            
            # Create transport
            self.transport = JsonRpcTransport(self.process)
            self.transport.start()
            
            # Register notification handlers
            self.transport.on_notification(
                'textDocument/publishDiagnostics',
                self._on_diagnostics
            )
            
            # Initialize
            return self._initialize()
            
        except Exception as e:
            logger.error(f"Failed to start language server: {e}")
            return False
    
    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists."""
        try:
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['where', cmd],
                    capture_output=True,
                    timeout=5
                )
            else:
                result = subprocess.run(
                    ['which', cmd],
                    capture_output=True,
                    timeout=5
                )
            return result.returncode == 0
        except:
            return False
    
    def _initialize(self) -> bool:
        """Send initialize request."""
        params = {
            'processId': os.getpid(),
            'rootUri': self.workspace_uri,
            'rootPath': self.workspace_root,
            'capabilities': {
                'textDocument': {
                    'hover': {
                        'contentFormat': ['markdown', 'plaintext']
                    },
                    'completion': {
                        'completionItem': {
                            'snippetSupport': True,
                            'documentationFormat': ['markdown', 'plaintext']
                        }
                    },
                    'definition': {
                        'linkSupport': True
                    },
                    'references': {},
                    'documentSymbol': {
                        'hierarchicalDocumentSymbolSupport': True
                    },
                    'publishDiagnostics': {
                        'relatedInformation': True
                    }
                },
                'workspace': {
                    'workspaceFolders': True,
                    'configuration': True
                }
            },
            'initializationOptions': self.config.initialization_options,
            'workspaceFolders': [
                {
                    'uri': self.workspace_uri,
                    'name': os.path.basename(self.workspace_root)
                }
            ]
        }
        
        result = self.transport.send_request('initialize', params)
        
        if result:
            # Send initialized notification
            self.transport.send_notification('initialized', {})
            self._initialized = True
            
            # Send workspace configuration if needed
            if self.config.settings:
                self._send_configuration()
            
            logger.info(f"LSP server initialized: {self.config.name}")
            return True
        
        return False
    
    def _send_configuration(self):
        """Send workspace configuration."""
        self.transport.send_notification('workspace/didChangeConfiguration', {
            'settings': self.config.settings
        })
    
    def stop(self):
        """Stop the language server."""
        if self.transport:
            try:
                self.transport.send_request('shutdown', timeout=5.0)
                self.transport.send_notification('exit')
            except:
                pass
            self.transport.stop()
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5.0)
            except:
                self.process.kill()
    
    def _on_diagnostics(self, params: Dict):
        """Handle diagnostics notification."""
        uri = params.get('uri', '')
        diagnostics = [Diagnostic.from_dict(d) for d in params.get('diagnostics', [])]
        self._diagnostics[uri] = diagnostics
    
    # =========================================================================
    # Document Management
    # =========================================================================
    
    def open_document(self, file_path: str, content: Optional[str] = None) -> bool:
        """Open a document in the language server."""
        if not self._initialized:
            return False
        
        uri = self._path_to_uri(file_path)
        
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return False
        
        self._open_documents[uri] = 1
        
        self.transport.send_notification('textDocument/didOpen', {
            'textDocument': {
                'uri': uri,
                'languageId': self.config.language_id,
                'version': 1,
                'text': content
            }
        })
        
        return True
    
    def close_document(self, file_path: str):
        """Close a document."""
        if not self._initialized:
            return
        
        uri = self._path_to_uri(file_path)
        
        if uri in self._open_documents:
            del self._open_documents[uri]
            self.transport.send_notification('textDocument/didClose', {
                'textDocument': {'uri': uri}
            })
    
    def update_document(self, file_path: str, content: str):
        """Update document content."""
        if not self._initialized:
            return
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path, content)
            return
        
        self._open_documents[uri] += 1
        version = self._open_documents[uri]
        
        self.transport.send_notification('textDocument/didChange', {
            'textDocument': {
                'uri': uri,
                'version': version
            },
            'contentChanges': [{'text': content}]
        })
    
    # =========================================================================
    # Code Intelligence Features
    # =========================================================================
    
    def get_definition(self, file_path: str, line: int, character: int) -> List[Location]:
        """Get definition location for a symbol."""
        if not self._initialized:
            return []
        
        uri = self._path_to_uri(file_path)
        
        # Ensure document is open
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)  # Wait for server to process
        
        result = self.transport.send_request('textDocument/definition', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character}
        })
        
        if not result:
            return []
        
        # Can be Location | Location[] | LocationLink[]
        if isinstance(result, dict):
            return [Location.from_dict(result)]
        elif isinstance(result, list):
            locations = []
            for item in result:
                if 'targetUri' in item:
                    # LocationLink
                    locations.append(Location(
                        uri=item['targetUri'],
                        range=Range.from_dict(item['targetRange'])
                    ))
                else:
                    locations.append(Location.from_dict(item))
            return locations
        
        return []
    
    def get_references(self, file_path: str, line: int, character: int, 
                       include_declaration: bool = True) -> List[Location]:
        """Get all references to a symbol."""
        if not self._initialized:
            return []
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/references', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character},
            'context': {'includeDeclaration': include_declaration}
        })
        
        if not result:
            return []
        
        return [Location.from_dict(loc) for loc in result]
    
    def get_hover(self, file_path: str, line: int, character: int) -> Optional[Hover]:
        """Get hover information."""
        if not self._initialized:
            return None
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/hover', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character}
        })
        
        if not result:
            return None
        
        return Hover.from_dict(result)
    
    def get_completions(self, file_path: str, line: int, character: int) -> List[CompletionItem]:
        """Get completion suggestions."""
        if not self._initialized:
            return []
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/completion', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character}
        })
        
        if not result:
            return []
        
        # Can be CompletionItem[] | CompletionList
        items = result.get('items', result) if isinstance(result, dict) else result
        
        return [CompletionItem.from_dict(item) for item in items]
    
    def get_document_symbols(self, file_path: str) -> List[DocumentSymbol]:
        """Get symbols in a document."""
        if not self._initialized:
            return []
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/documentSymbol', {
            'textDocument': {'uri': uri}
        })
        
        if not result:
            return []
        
        # Can be DocumentSymbol[] or SymbolInformation[]
        if result and 'range' in result[0]:
            return [DocumentSymbol.from_dict(s) for s in result]
        else:
            # Convert SymbolInformation to DocumentSymbol
            symbols = []
            for s in result:
                info = SymbolInformation.from_dict(s)
                symbols.append(DocumentSymbol(
                    name=info.name,
                    kind=info.kind,
                    range=info.location.range,
                    selection_range=info.location.range,
                    detail=info.container_name
                ))
            return symbols
    
    def get_workspace_symbols(self, query: str = '') -> List[SymbolInformation]:
        """Search for symbols in the workspace."""
        if not self._initialized:
            return []
        
        result = self.transport.send_request('workspace/symbol', {
            'query': query
        })
        
        if not result:
            return []
        
        return [SymbolInformation.from_dict(s) for s in result]
    
    def get_type_definition(self, file_path: str, line: int, character: int) -> List[Location]:
        """Get type definition location."""
        if not self._initialized:
            return []
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/typeDefinition', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character}
        })
        
        if not result:
            return []
        
        if isinstance(result, dict):
            return [Location.from_dict(result)]
        return [Location.from_dict(loc) for loc in result]
    
    def get_implementation(self, file_path: str, line: int, character: int) -> List[Location]:
        """Get implementation locations."""
        if not self._initialized:
            return []
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/implementation', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character}
        })
        
        if not result:
            return []
        
        if isinstance(result, dict):
            return [Location.from_dict(result)]
        return [Location.from_dict(loc) for loc in result]
    
    def get_diagnostics(self, file_path: str) -> List[Diagnostic]:
        """Get diagnostics for a file."""
        uri = self._path_to_uri(file_path)
        return self._diagnostics.get(uri, [])
    
    def format_document(self, file_path: str) -> Optional[List[Dict]]:
        """Format a document."""
        if not self._initialized:
            return None
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/formatting', {
            'textDocument': {'uri': uri},
            'options': {
                'tabSize': 4,
                'insertSpaces': True
            }
        })
        
        return result
    
    def rename_symbol(self, file_path: str, line: int, character: int, 
                      new_name: str) -> Optional[Dict]:
        """Rename a symbol across the workspace."""
        if not self._initialized:
            return None
        
        uri = self._path_to_uri(file_path)
        
        if uri not in self._open_documents:
            self.open_document(file_path)
            time.sleep(0.5)
        
        result = self.transport.send_request('textDocument/rename', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character},
            'newName': new_name
        })
        
        return result


# =============================================================================
# LSP Manager
# =============================================================================

class LSPManager:
    """
    Manages multiple LSP clients for different languages.
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self.clients: Dict[str, LSPClient] = {}
        self._started = False
    
    def get_language_for_file(self, file_path: str) -> Optional[str]:
        """Determine the language for a file."""
        ext = os.path.splitext(file_path)[1].lower()
        
        for lang, config in LANGUAGE_SERVERS.items():
            if ext in config.file_extensions:
                return lang
        
        return None
    
    def start_server(self, language: str) -> bool:
        """Start a language server."""
        if language in self.clients:
            return True
        
        if language not in LANGUAGE_SERVERS:
            logger.warning(f"No language server configured for: {language}")
            return False
        
        config = LANGUAGE_SERVERS[language]
        client = LSPClient(config, self.workspace_root)
        
        if client.start():
            self.clients[language] = client
            return True
        
        return False
    
    def start_all_available(self) -> Dict[str, bool]:
        """Start all available language servers."""
        results = {}
        for language in LANGUAGE_SERVERS:
            results[language] = self.start_server(language)
        self._started = True
        return results
    
    def stop_all(self):
        """Stop all language servers."""
        for client in self.clients.values():
            try:
                client.stop()
            except:
                pass
        self.clients.clear()
        self._started = False
    
    def get_client(self, file_path: str) -> Optional[LSPClient]:
        """Get the appropriate client for a file."""
        language = self.get_language_for_file(file_path)
        if language and language in self.clients:
            return self.clients[language]
        
        # Try to start the server
        if language and self.start_server(language):
            return self.clients.get(language)
        
        return None
    
    def get_definition(self, file_path: str, line: int, character: int) -> List[Dict]:
        """Get definition using appropriate client."""
        client = self.get_client(file_path)
        if not client:
            return []
        
        locations = client.get_definition(file_path, line, character)
        return [
            {
                'uri': loc.uri,
                'path': client._uri_to_path(loc.uri),
                'range': {
                    'start': {'line': loc.range.start.line, 'character': loc.range.start.character},
                    'end': {'line': loc.range.end.line, 'character': loc.range.end.character}
                }
            }
            for loc in locations
        ]
    
    def get_references(self, file_path: str, line: int, character: int) -> List[Dict]:
        """Get references using appropriate client."""
        client = self.get_client(file_path)
        if not client:
            return []
        
        locations = client.get_references(file_path, line, character)
        return [
            {
                'uri': loc.uri,
                'path': client._uri_to_path(loc.uri),
                'range': {
                    'start': {'line': loc.range.start.line, 'character': loc.range.start.character},
                    'end': {'line': loc.range.end.line, 'character': loc.range.end.character}
                }
            }
            for loc in locations
        ]
    
    def get_hover(self, file_path: str, line: int, character: int) -> Optional[Dict]:
        """Get hover info using appropriate client."""
        client = self.get_client(file_path)
        if not client:
            return None
        
        hover = client.get_hover(file_path, line, character)
        if not hover:
            return None
        
        # Extract text from contents
        contents = hover.contents
        if isinstance(contents, dict):
            text = contents.get('value', str(contents))
        elif isinstance(contents, list):
            text = '\n'.join(
                c.get('value', str(c)) if isinstance(c, dict) else str(c)
                for c in contents
            )
        else:
            text = str(contents)
        
        return {
            'contents': text,
            'range': hover.range.to_dict() if hover.range else None
        }
    
    def get_completions(self, file_path: str, line: int, character: int) -> List[Dict]:
        """Get completions using appropriate client."""
        client = self.get_client(file_path)
        if not client:
            return []
        
        items = client.get_completions(file_path, line, character)
        return [
            {
                'label': item.label,
                'kind': item.kind.name if item.kind else None,
                'detail': item.detail,
                'documentation': item.documentation,
                'insertText': item.insert_text
            }
            for item in items
        ]
    
    def get_document_symbols(self, file_path: str) -> List[Dict]:
        """Get document symbols using appropriate client."""
        client = self.get_client(file_path)
        if not client:
            return []
        
        def symbol_to_dict(symbol: DocumentSymbol, parent_path: str = '') -> Dict:
            path = f"{parent_path}.{symbol.name}" if parent_path else symbol.name
            result = {
                'name': symbol.name,
                'kind': symbol.kind.name,
                'path': path,
                'detail': symbol.detail,
                'range': symbol.range.to_dict(),
                'selectionRange': symbol.selection_range.to_dict(),
                'children': [symbol_to_dict(c, path) for c in symbol.children]
            }
            return result
        
        symbols = client.get_document_symbols(file_path)
        return [symbol_to_dict(s) for s in symbols]
    
    def get_workspace_symbols(self, query: str = '') -> List[Dict]:
        """Search for symbols across all clients."""
        results = []
        
        for lang, client in self.clients.items():
            symbols = client.get_workspace_symbols(query)
            for s in symbols:
                results.append({
                    'name': s.name,
                    'kind': s.kind.name,
                    'language': lang,
                    'containerName': s.container_name,
                    'path': client._uri_to_path(s.location.uri),
                    'range': s.location.range.to_dict()
                })
        
        return results
    
    def get_diagnostics(self, file_path: str) -> List[Dict]:
        """Get diagnostics for a file."""
        client = self.get_client(file_path)
        if not client:
            return []
        
        diagnostics = client.get_diagnostics(file_path)
        return [
            {
                'range': d.range.to_dict(),
                'message': d.message,
                'severity': d.severity,
                'code': d.code,
                'source': d.source
            }
            for d in diagnostics
        ]
    
    def get_status(self) -> Dict:
        """Get status of all language servers."""
        return {
            'workspace': self.workspace_root,
            'started': self._started,
            'servers': {
                lang: {
                    'name': client.config.name,
                    'initialized': client._initialized,
                    'open_documents': len(client._open_documents)
                }
                for lang, client in self.clients.items()
            },
            'available_servers': list(LANGUAGE_SERVERS.keys())
        }


# =============================================================================
# Convenience Functions
# =============================================================================

_global_manager: Optional[LSPManager] = None


def get_lsp_manager(workspace_root: str) -> LSPManager:
    """Get or create the global LSP manager."""
    global _global_manager
    
    if _global_manager is None or _global_manager.workspace_root != os.path.abspath(workspace_root):
        if _global_manager:
            _global_manager.stop_all()
        _global_manager = LSPManager(workspace_root)
    
    return _global_manager


def start_lsp_servers(workspace_root: str) -> Dict[str, bool]:
    """Start all available LSP servers."""
    manager = get_lsp_manager(workspace_root)
    return manager.start_all_available()


def stop_lsp_servers():
    """Stop all LSP servers."""
    global _global_manager
    if _global_manager:
        _global_manager.stop_all()
        _global_manager = None


def goto_definition(workspace_root: str, file_path: str, line: int, character: int) -> List[Dict]:
    """Go to definition."""
    manager = get_lsp_manager(workspace_root)
    return manager.get_definition(file_path, line, character)


def find_references(workspace_root: str, file_path: str, line: int, character: int) -> List[Dict]:
    """Find all references."""
    manager = get_lsp_manager(workspace_root)
    return manager.get_references(file_path, line, character)


def get_hover_info(workspace_root: str, file_path: str, line: int, character: int) -> Optional[Dict]:
    """Get hover information."""
    manager = get_lsp_manager(workspace_root)
    return manager.get_hover(file_path, line, character)


def get_completions(workspace_root: str, file_path: str, line: int, character: int) -> List[Dict]:
    """Get code completions."""
    manager = get_lsp_manager(workspace_root)
    return manager.get_completions(file_path, line, character)


def get_symbols(workspace_root: str, file_path: str) -> List[Dict]:
    """Get document symbols."""
    manager = get_lsp_manager(workspace_root)
    return manager.get_document_symbols(file_path)


def search_symbols(workspace_root: str, query: str) -> List[Dict]:
    """Search workspace symbols."""
    manager = get_lsp_manager(workspace_root)
    return manager.get_workspace_symbols(query)
