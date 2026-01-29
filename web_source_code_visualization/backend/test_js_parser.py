"""
Test script for enhanced JavaScript parser.
Tests DOM XSS detection, API calls, event handlers, and input sources.
"""

import sys
sys.path.insert(0, 'c:/Users/dntmd/OneDrive/Desktop/my/Project/web_source_code_visualization/backend')

from core.parser.javascript import JavaScriptParser

# Sample JavaScript code with various security-related patterns
TEST_JS_CODE = '''
// Express.js route handler
app.get('/search', (req, res) => {
    const query = req.query.q;
    const userId = req.params.id;
    const data = req.body.data;
    
    // DOM XSS Sink - innerHTML
    document.getElementById('results').innerHTML = query;
    
    // DOM XSS Sink - outerHTML
    element.outerHTML = data;
    
    // Code injection
    eval(query);
    
    // API calls
    fetch('/api/search?q=' + query);
    
    axios.get('/api/users/' + userId);
    
    $.ajax('/api/data', { method: 'POST' });
    
    // Event handler
    document.getElementById('btn').addEventListener('click', handleClick);
    
    // URL parameters
    const params = new URLSearchParams(window.location.search);
    const name = params.get('name');
    
    // Location-based sources
    const hash = location.hash;
    const path = location.pathname;
    
    // setTimeout with string (potential issue)
    setTimeout('alert(1)', 1000);
});

// React component
function UserProfile({ userId }) {
    const [user, setUser] = useState(null);
    
    useEffect(() => {
        axios.post('/api/user/' + userId, { action: 'fetch' });
    }, [userId]);
    
    const handleSubmit = () => {
        fetch('/api/update', {
            method: 'POST',
            body: JSON.stringify(user)
        });
    };
    
    return (
        <div onClick={handleSubmit}>
            <div dangerouslySetInnerHTML={{ __html: user?.bio }} />
        </div>
    );
}

// Dangerous document.write
document.write('<script>' + userInput + '</script>');
'''

def test_js_parser():
    parser = JavaScriptParser()
    
    # Check if can parse JS
    print("=" * 60)
    print("JavaScript Parser Enhancement Test")
    print("=" * 60)
    
    assert parser.can_parse("test.js") == True
    assert parser.can_parse("test.jsx") == True
    assert parser.can_parse("test.ts") == True
    assert parser.can_parse("test.tsx") == True
    assert parser.can_parse("test.py") == False
    print("[PASS] can_parse() works correctly")
    
    # Parse the test code
    endpoints = parser.parse("test.js", TEST_JS_CODE)
    
    print(f"\n[INFO] Found {len(endpoints)} endpoint(s)")
    
    for ep in endpoints:
        print(f"\n{'=' * 50}")
        print(f"Root: {ep.path} (type: {ep.type})")
        print(f"{'=' * 50}")
        
        # Check inputs
        print(f"\n[INPUTS] ({len(ep.params)} found):")
        for param in ep.params:
            print(f"  - {param.name} (type: {param.type}, source: {getattr(param, 'source', 'N/A')})")
        
        # Check children by type
        api_calls = [c for c in ep.children if c.type == "api_call"]
        sinks = [c for c in ep.children if c.type == "sink"]
        events = [c for c in ep.children if c.type == "event_handler"]
        calls = [c for c in ep.children if c.type == "call"]
        
        print(f"\n[API CALLS] ({len(api_calls)} found):")
        for call in api_calls:
            print(f"  - {call.path} (line: {call.line_number})")
            
        print(f"\n[DOM SINKS] ({len(sinks)} found):")
        for sink in sinks:
            severity = sink.metadata.get("severity", "N/A")
            dangerous = "⚠️ DANGEROUS" if sink.metadata.get("dangerous") else ""
            print(f"  - {sink.path} (severity: {severity}) {dangerous}")
            
        print(f"\n[EVENT HANDLERS] ({len(events)} found):")
        for event in events:
            print(f"  - {event.path} (line: {event.line_number})")
            
        print(f"\n[FUNCTION CALLS] ({len(calls)} found):")
        for call in calls[:5]:  # Show first 5
            print(f"  - {call.path}")
        if len(calls) > 5:
            print(f"  ... and {len(calls) - 5} more")
        
        # Check metadata
        print(f"\n[METADATA]:")
        print(f"  - Inputs count: {ep.metadata.get('inputs_count', 0)}")
        print(f"  - API calls count: {ep.metadata.get('api_calls_count', 0)}")
        print(f"  - DOM sinks count: {ep.metadata.get('dom_sinks_count', 0)}")
        print(f"  - Has dangerous sinks: {ep.metadata.get('has_dangerous_sinks', False)}")
    
    # Verify expected findings
    root = endpoints[0]
    
    # Expected inputs - check for URL sources that we detect
    assert any("location" in p.name for p in root.params), "Should find location-based sources"
    assert any(p.type == "URLParam" for p in root.params), "Should find URLSearchParams"
    print("\n[PASS] Input detection works")
    
    # Expected sinks
    sink_names = [s.metadata.get("sink_name") for s in sinks]
    assert "innerHTML" in sink_names, "Should detect innerHTML"
    assert "eval" in sink_names, "Should detect eval"
    print("[PASS] Sink detection works")
    
    # Expected API calls
    api_types = [a.metadata.get("api_type") for a in api_calls]
    assert "fetch" in api_types, "Should detect fetch calls"
    assert "axios" in api_types, "Should detect axios calls"
    print("[PASS] API call detection works")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    test_js_parser()
