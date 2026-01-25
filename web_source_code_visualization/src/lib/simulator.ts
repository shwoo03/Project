
// Virtual File System
const virtualFS: Record<string, string> = {
    '/': '[DIR] bin, etc, var, home, root, flag',
    '/flag': 'DH{S0urc3_V1z_H4ck3d_Succ3ssfully!}',
    '/etc/passwd': 'root:x:0:0:root:/root:/bin/bash\nwraith:x:1000:1000:wraith:/home/wraith:/bin/bash',
    '/home/wraith/secret.txt': 'My super secret diary...',
    'flag': 'DH{S0urc3_V1z_H4ck3d_Succ3ssfully!}', // Relative path alias
    'flag.txt': 'DH{S0urc3_V1z_H4ck3d_Succ3ssfully!}',
};

export interface SimulationResult {
    output: string;
    success: boolean;
    step: string; // "Executed command" or "File read"
}

export function simulateExploit(vulnType: string, payload: string | Record<string, string>): SimulationResult {
    // Normalize payload to string for regex checks, but keep object for logic
    const pStr = typeof payload === 'string' ? payload : JSON.stringify(payload);
    const pObj = typeof payload === 'object' ? payload : { param: payload };

    // 1. RCE Simulation (Command Injection)
    if (vulnType === 'RCE' || vulnType === 'Command Injection') {
        const cmdVal = Object.values(pObj).join(' '); // Search all params
        // ... (existing RCE logic using cmdVal) ...
        const p = cmdVal; // Alias for legacy logic below
        // Simple command parser
        // Supports: cat, ls, whoami, id

        // Remove common injection separators like ;, |, ||, &&, $()
        const command = p.replace(/[;&|]|\$\(|\)/g, ' ').trim();
        const parts = command.split(/\s+/);
        const bin = parts[parts.length - 1] === 'cat' || parts[parts.length - 1] === 'ls' ? parts[parts.length - 1] : parts[0];
        // Heuristic: users often type "; cat /flag", so we look for the last valid command

        // Handle "; cat /flag" -> cmd="cat", args="/flag"
        // Let's implement a simpler "contains" logic for demo

        if (p.includes('cat')) {
            // Extract filename after cat
            const match = p.match(/cat\s+([^\s;&|]+)/);
            const file = match ? match[1] : 'flag';
            const content = virtualFS[file] || virtualFS['/' + file] || `cat: ${file}: No such file or directory`;
            return {
                output: content,
                success: content.includes('DH{'),
                step: `Executed shell command: '${p}'`
            };
        }

        if (p.includes('ls')) {
            return { output: 'flag.txt\nindex.php\nadmin.php\nrobots.txt', success: true, step: `Executed shell command: '${p}'` };
        }

        if (p.includes('whoami')) return { output: 'www-data', success: true, step: `Executed shell command: '${p}'` };
        if (p.includes('id')) return { output: 'uid=33(www-data) gid=33(www-data) groups=33(www-data)', success: true, step: `Executed shell command: '${p}'` };

        return { output: `/bin/sh: ${p}: command not found`, success: false, step: `Executed shell command: '${p}'` };
    }

    // 2. Path Traversal / LFI
    if (vulnType === 'PathTraversal' || vulnType === 'LFI') {
        if (pStr.includes('..') || pStr.includes('/')) {
            const target = pStr.includes('flag') ? '/flag' : '/etc/passwd';
            const content = virtualFS[target] || virtualFS['/flag'];
            return {
                output: content,
                success: true,
                step: `Server read file: '${target}'`
            };
        }
    }

    // 3. SQL Injection
    if (vulnType === 'SQLi') {
        if (pStr.includes("'") || pStr.includes('"')) {
            if (pStr.toLowerCase().includes('or 1=1') || pStr.includes('#') || pStr.includes('--')) {
                return {
                    output: `[ { "id": 1, "user": "admin", "pass": "DH{S0urc3_V1z_H4ck3d_Succ3ssfully!}" }, { "id": 2, "user": "guest", "pass": "guest" } ]`,
                    success: true,
                    step: `Database Query Executed: SELECT * FROM users WHERE user = '${Object.values(pObj)[0]}'`
                };
            }
            return { output: "SQL Syntax Error: You have an error in your SQL syntax...", success: false, step: "Database Syntax Error" };
        }
    }

    // 4. Broken Access Control / Insecure Auth (e.g. Cookie Manipulation)
    if (vulnType === 'InsecureAuth' || vulnType === 'Broken Access Control') {
        if (pStr.includes('admin') || pStr.includes('true')) {
            return {
                output: "Hello admin, flag is DH{C00k13_M4n1pul4t10n_Success}",
                success: true,
                step: "Auth Bypass Successful (Admin)"
            };
        }
        if (pStr.includes('guest')) {
            return {
                output: "Hello guest, you are not admin",
                success: true,
                step: "Cookie Accepted (Guest)"
            };
        }
    }

    // 5. Login / Auth Check
    const user = pObj['username'] || pObj['user'];
    const pass = pObj['password'] || pObj['pass'];

    if (user && pass) {
        if (user === 'guest' && pass === 'guest') {
            return {
                output: "Login Successful. Welcome, Guest!",
                success: true,
                step: "302 Redirect -> /dashboard"
            };
        }
        if (user === 'admin' && pass === 'admin123') { // Simple mock
            return {
                output: "Login Successful. Welcome, Administrator!",
                success: true,
                step: "302 Redirect -> /admin"
            };
        }
        return { output: "Invalid Credentials.", success: false, step: "401 Unauthorized" };
    }

    // Fallback
    if (pStr.length > 0) {
        if (pStr === 'admin') return { output: "Password required for user 'admin'", success: false, step: "Login Attempt" };
        return { output: "Invalid Input.", success: false, step: "400 Bad Request" };
    }

    // Default
    return { output: "Simulator waiting...", success: false, step: "Idle" };
}
