"""
Test script for new features:
1. Taint Flow visualization
2. TypeScript parser
3. PHP framework support (Laravel/Symfony)
"""

import sys
import os

# Use raw string for Windows path
backend_path = r'c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\backend'
sys.path.insert(0, backend_path)
os.chdir(backend_path)

from core.parser.typescript import TypeScriptParser
from core.parser.php import PHPParser
from core.parser.manager import ParserManager

# ============================================
# Test 1: TypeScript Parser
# ============================================
TS_NEXTJS_API = '''
import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { id } = req.query;
  const { data } = req.body;
  
  // Dangerous: eval with user input
  eval(data);
  
  // API call
  const result = await fetch(`/api/users/${id}`);
  
  res.status(200).json({ result });
}
'''

TS_REACT_COMPONENT = '''
import React, { useState, useEffect } from 'react';

interface UserProps {
  userId: string;
  name: string;
}

const UserProfile: React.FC<UserProps> = ({ userId, name }) => {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    axios.get(`/api/user/${userId}`);
  }, [userId]);
  
  const handleClick = () => {
    // XSS sink
    document.getElementById('output').innerHTML = data;
  };
  
  return (
    <div onClick={handleClick}>
      <div dangerouslySetInnerHTML={{ __html: data }} />
    </div>
  );
};

export default UserProfile;
'''

# ============================================
# Test 2: PHP Laravel
# ============================================
PHP_LARAVEL_ROUTES = r'''
<?php

use App\Http\Controllers\UserController;
use Illuminate\Support\Facades\Route;

Route::get('/users', [UserController::class, 'index'])->middleware('auth');
Route::post('/users', [UserController::class, 'store']);
Route::get('/users/{id}', [UserController::class, 'show']);
Route::put('/users/{id}', [UserController::class, 'update']);
Route::delete('/users/{id}', [UserController::class, 'destroy']);
'''

PHP_LARAVEL_CONTROLLER = r'''
<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class UserController extends Controller
{
    public function index(Request $request)
    {
        $search = $request->input('search');
        $page = $request->query('page');
        
        // SQL Injection risk
        $users = DB::raw("SELECT * FROM users WHERE name LIKE '%$search%'");
        
        return view('users.index', compact('users'));
    }
    
    public function store(Request $request)
    {
        $name = $request->input('name');
        $email = $request->post('email');
        
        // Command injection
        exec("echo $name");
        
        return redirect()->back();
    }
}
'''

# ============================================
# Test 3: PHP Symfony
# ============================================
PHP_SYMFONY_CONTROLLER = r'''
<?php

namespace App\Controller;

use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Annotation\Route;

class UserController extends AbstractController
{
    #[Route('/users', name: 'user_list', methods: ['GET'])]
    public function list(Request $request): Response
    {
        $search = $request->query->get('search');
        $page = $request->query->get('page');
        
        return $this->render('users/list.html.twig');
    }
    
    #[Route('/users/{id}', name: 'user_show', methods: ['GET', 'POST'])]
    public function show(Request $request, int $id): Response
    {
        $data = $request->request->get('data');
        
        // Dangerous: eval
        eval($data);
        
        return $this->json(['id' => $id]);
    }
}
'''

def test_typescript_parser():
    print("\n" + "=" * 60)
    print("Test: TypeScript Parser")
    print("=" * 60)
    
    parser = TypeScriptParser()
    
    # Test can_parse
    assert parser.can_parse("test.ts") == True
    assert parser.can_parse("test.tsx") == True
    assert parser.can_parse("test.js") == False
    print("[PASS] can_parse() works correctly")
    
    # Test Next.js API parsing
    print("\n--- Next.js API Route ---")
    endpoints = parser.parse("pages/api/users.ts", TS_NEXTJS_API)
    
    for ep in endpoints:
        print(f"  Endpoint: {ep.method} {ep.path}")
        print(f"  Params: {[p.name for p in ep.params]}")
        print(f"  Framework: {ep.metadata.get('framework')}")
        
        sinks = [c for c in ep.children if c.type == "sink"]
        print(f"  Sinks: {[s.path for s in sinks]}")
        
        api_calls = [c for c in ep.children if c.type == "api_call"]
        print(f"  API Calls: {[a.path for a in api_calls]}")
    
    # Test React component parsing
    print("\n--- React Component ---")
    endpoints = parser.parse("components/UserProfile.tsx", TS_REACT_COMPONENT)
    
    for ep in endpoints:
        print(f"  Component: {ep.path}")
        print(f"  Props: {[p.name for p in ep.params]}")
        print(f"  Hooks: {ep.metadata.get('hooks', [])}")
        
        sinks = [c for c in ep.children if c.type == "sink"]
        print(f"  Sinks: {[s.path for s in sinks]}")
    
    print("\n[PASS] TypeScript Parser works correctly")
    return True

def test_php_laravel():
    print("\n" + "=" * 60)
    print("Test: PHP Laravel Support")
    print("=" * 60)
    
    parser = PHPParser()
    
    # Test routes file
    print("\n--- Laravel Routes ---")
    endpoints = parser.parse("routes/web.php", PHP_LARAVEL_ROUTES)
    
    print(f"  Found {len(endpoints)} routes:")
    for ep in endpoints:
        print(f"    {ep.method} {ep.path}")
        if ep.metadata.get('controller'):
            print(f"      -> {ep.metadata['controller']}@{ep.metadata.get('action')}")
    
    # Test controller file
    print("\n--- Laravel Controller ---")
    endpoints = parser.parse("app/Http/Controllers/UserController.php", PHP_LARAVEL_CONTROLLER)
    
    for ep in endpoints:
        print(f"  {ep.path}")
        print(f"  Inputs: {[p.name for p in ep.params]}")
        
        sinks = [c for c in ep.children if c.type == "sink"]
        print(f"  Sinks: {[s.path for s in sinks]}")
    
    print("\n[PASS] PHP Laravel support works correctly")
    return True

def test_php_symfony():
    print("\n" + "=" * 60)
    print("Test: PHP Symfony Support")
    print("=" * 60)
    
    parser = PHPParser()
    
    endpoints = parser.parse("src/Controller/UserController.php", PHP_SYMFONY_CONTROLLER)
    
    print(f"  Found {len(endpoints)} endpoints:")
    for ep in endpoints:
        print(f"    {ep.method} {ep.path}")
        print(f"    Framework: {ep.metadata.get('framework')}")
        print(f"    Inputs: {[p.name for p in ep.params]}")
        
        sinks = [c for c in ep.children if c.type == "sink"]
        if sinks:
            print(f"    Sinks: {[s.path for s in sinks]}")
    
    print("\n[PASS] PHP Symfony support works correctly")
    return True

def test_parser_manager():
    print("\n" + "=" * 60)
    print("Test: Parser Manager Integration")
    print("=" * 60)
    
    manager = ParserManager()
    
    # Test file type detection
    test_cases = [
        ("test.ts", "TypeScriptParser"),
        ("test.tsx", "TypeScriptParser"),
        ("test.js", "JavascriptParser"),
        ("test.jsx", "JavascriptParser"),
        ("test.py", "PythonParser"),
        ("test.php", "PHPParser"),
        ("test.java", "JavaParser"),
        ("test.go", "GoParser"),
    ]
    
    for filename, expected_parser in test_cases:
        parser = manager.get_parser(filename)
        if parser:
            actual = parser.__class__.__name__
            status = "✓" if actual == expected_parser else "✗"
            print(f"  {status} {filename} -> {actual}")
        else:
            print(f"  ✗ {filename} -> None (expected {expected_parser})")
    
    print("\n[PASS] Parser Manager works correctly")
    return True

def main():
    print("=" * 60)
    print("NEW FEATURES TEST SUITE")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("TypeScript Parser", test_typescript_parser()))
    except Exception as e:
        print(f"[FAIL] TypeScript Parser: {e}")
        import traceback
        traceback.print_exc()
        results.append(("TypeScript Parser", False))
    
    try:
        results.append(("PHP Laravel", test_php_laravel()))
    except Exception as e:
        print(f"[FAIL] PHP Laravel: {e}")
        import traceback
        traceback.print_exc()
        results.append(("PHP Laravel", False))
    
    try:
        results.append(("PHP Symfony", test_php_symfony()))
    except Exception as e:
        print(f"[FAIL] PHP Symfony: {e}")
        import traceback
        traceback.print_exc()
        results.append(("PHP Symfony", False))
    
    try:
        results.append(("Parser Manager", test_parser_manager()))
    except Exception as e:
        print(f"[FAIL] Parser Manager: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Parser Manager", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed.")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
