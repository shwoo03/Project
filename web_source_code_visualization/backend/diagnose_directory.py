#!/usr/bin/env python3
"""
Diagnostic tool for analyzing stuck directories
"""
import os
import sys
import time
import traceback

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from core.parser import ParserManager
from core.symbol_table import SymbolTable, Symbol, SymbolType

def diagnose_directory(directory_path):
    """Complete diagnostic analysis of a directory"""
    
    print("=" * 80)
    print(" Directory Analysis Diagnostic Tool")
    print("=" * 80)
    print()
    
    # Step 1: Path validation
    print("[1] Path Validation")
    print("-" * 80)
    print(f"Path: {directory_path}")
    
    if not os.path.exists(directory_path):
        print("❌ ERROR: Path does not exist!")
        return False
    print("✅ Path exists")
    
    if not os.path.isdir(directory_path):
        print("❌ ERROR: Path is not a directory!")
        return False
    print("✅ Path is a directory")
    
    try:
        # Normalize path for Unicode
        normalized_path = os.path.normpath(directory_path)
        print(f"✅ Normalized path: {normalized_path}")
    except Exception as e:
        print(f"❌ ERROR normalizing path: {e}")
        return False
    
    print()
    
    # Step 2: File discovery
    print("[2] File Discovery")
    print("-" * 80)
    
    all_files = []
    skip_dirs = {'venv', 'node_modules', '.git', '__pycache__'}
    supported_exts = {'.py', '.js', '.jsx', '.ts', '.tsx', '.php', '.java', '.go'}
    
    try:
        for root, dirs, files in os.walk(normalized_path):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1].lower()
                
                if ext in supported_exts:
                    # Check if file is readable
                    try:
                        is_readable = os.access(file_path, os.R_OK)
                        file_size = os.path.getsize(file_path)
                        
                        all_files.append({
                            'path': file_path,
                            'ext': ext,
                            'size': file_size,
                            'readable': is_readable
                        })
                        
                        print(f"  Found: {os.path.basename(file_path)} ({ext}, {file_size} bytes, readable: {is_readable})")
                    except Exception as e:
                        print(f"  ⚠️ Error accessing {filename}: {e}")
    except Exception as e:
        print(f"❌ ERROR walking directory: {e}")
        traceback.print_exc()
        return False
    
    print(f"\n✅ Found {len(all_files)} parseable files")
    print()
    
    if len(all_files) == 0:
        print("⚠️ No parseable files found!")
        return True
    
    # Step 3: Parser initialization
    print("[3] Parser Initialization")
    print("-" * 80)
    
    try:
        parser_manager = ParserManager()
        print("✅ Parser manager initialized")
    except Exception as e:
        print(f"❌ ERROR initializing parser manager: {e}")
        traceback.print_exc()
        return False
    
    print()
    
    # Step 4: Symbol scanning phase
    print("[4] Symbol Scanning Phase")
    print("-" * 80)
    
    global_symbols = {}
    symbol_table = SymbolTable()
    scan_errors = []
    
    for idx, file_info in enumerate(all_files):
        file_path = file_info['path']
        filename = os.path.basename(file_path)
        
        print(f"  [{idx+1}/{len(all_files)}] Scanning {filename}...", end=' ')
        
        parser = parser_manager.get_parser(file_path)
        if not parser:
            print("⚠️ No parser available")
            continue
        
        try:
            start_time = time.time()
            
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            read_time = time.time() - start_time
            
            # Scan symbols
            scan_start = time.time()
            symbols = parser.scan_symbols(file_path, content)
            scan_time = time.time() - scan_start
            
            global_symbols.update(symbols)
            
            # Add to symbol table
            for name, info in symbols.items():
                sym_type = SymbolType.FUNCTION
                if info.get("type") == "class":
                    sym_type = SymbolType.CLASS
                elif info.get("type") == "variable":
                    sym_type = SymbolType.VARIABLE
                
                symbol_table.add(Symbol(
                    name=name,
                    full_name=name,
                    type=sym_type,
                    file_path=file_path,
                    line_number=info.get("start_line", 0),
                    end_line_number=info.get("end_line", 0),
                    inherits_from=info.get("inherits", [])
                ))
            
            total_time = time.time() - start_time
            print(f"✅ {len(symbols)} symbols (read: {read_time:.3f}s, scan: {scan_time:.3f}s, total: {total_time:.3f}s)")
            
        except (UnicodeDecodeError, IOError, OSError) as file_err:
            print(f"❌ File error: {file_err}")
            scan_errors.append((filename, str(file_err)))
        except Exception as e:
            print(f"❌ Parse error: {e}")
            scan_errors.append((filename, str(e)))
    
    print(f"\n✅ Symbol scan complete: {len(global_symbols)} symbols, {len(scan_errors)} errors")
    print()
    
    # Step 5: Full parsing phase
    print("[5] Full Parsing Phase")
    print("-" * 80)
    
    all_endpoints = []
    parse_errors = []
    
    for idx, file_info in enumerate(all_files):
        file_path = file_info['path']
        filename = os.path.basename(file_path)
        
        print(f"  [{idx+1}/{len(all_files)}] Parsing {filename}...", end=' ')
        
        parser = parser_manager.get_parser(file_path)
        if not parser:
            print("⚠️ No parser")
            continue
        
        try:
            start_time = time.time()
            
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse
            endpoints = parser.parse(
                file_path, content,
                global_symbols=global_symbols,
                symbol_table=symbol_table
            )
            
            all_endpoints.extend(endpoints)
            
            parse_time = time.time() - start_time
            print(f"✅ {len(endpoints)} endpoints ({parse_time:.3f}s)")
            
        except (UnicodeDecodeError, IOError, OSError) as file_err:
            print(f"❌ File error: {file_err}")
            parse_errors.append((filename, str(file_err)))
        except Exception as e:
            print(f"❌ Parse error: {e}")
            parse_errors.append((filename, str(e)))
            traceback.print_exc()
    
    print(f"\n✅ Parsing complete: {len(all_endpoints)} endpoints, {len(parse_errors)} errors")
    print()
    
    # Step 6: Summary
    print("[6] Summary")
    print("-" * 80)
    print(f"Total files found:    {len(all_files)}")
    print(f"Symbols discovered:   {len(global_symbols)}")
    print(f"Endpoints created:    {len(all_endpoints)}")
    print(f"Scan errors:          {len(scan_errors)}")
    print(f"Parse errors:         {len(parse_errors)}")
    
    if scan_errors:
        print("\nScan Errors:")
        for filename, error in scan_errors:
            print(f"  - {filename}: {error}")
    
    if parse_errors:
        print("\nParse Errors:")
        for filename, error in parse_errors:
            print(f"  - {filename}: {error}")
    
    print()
    print("=" * 80)
    print("✅ Diagnostic Complete!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    # Test paths
    test_paths = [
        r"c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\새싹\cookie",
        r"C:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\cookie"
    ]
    
    for test_path in test_paths:
        print(f"\n\nTesting: {test_path}\n")
        if os.path.exists(test_path):
            diagnose_directory(test_path)
            print("\n" + "=" * 80 + "\n")
        else:
            print(f"⚠️ Path does not exist: {test_path}\n")
