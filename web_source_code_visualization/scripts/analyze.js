const fs = require('fs');
const path = require('path');
const glob = require('glob');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

// Load Rules
const rulesDir = path.join(__dirname, 'rules');
let rules = [];
if (fs.existsSync(rulesDir)) {
    console.error(`Loading rules from ${rulesDir}`);
    fs.readdirSync(rulesDir).forEach(file => {
        if (file.endsWith('.js')) {
            try {
                const rule = require(path.join(rulesDir, file));
                rules.push(rule);
                console.error(`Loaded rule: ${rule.name}`);
            } catch (e) {
                console.error(`Failed to load rule ${file}: ${e.message}`);
            }
        }
    });
}

// Clean argument path for Windows
let targetDir = process.argv[2] || '.';
targetDir = targetDir.replace(/\\/g, '/');

console.error(`Analyzing directory: ${targetDir} with ${rules.length} rules.`);

const files = glob.sync('**/*.{js,ts,py,html}', {
    cwd: targetDir,
    ignore: ['**/node_modules/**', '**/dist/**', '**/.next/**', '**/__pycache__/**'],
    absolute: true
});

const routes = [];

files.forEach(filePath => {
    try {
        const code = fs.readFileSync(filePath, 'utf-8');
        const ext = path.extname(filePath);

        // --- JavaScript / TypeScript Analysis (AST) ---
        if (['.js', '.ts', '.tsx', '.jsx'].includes(ext)) {
            const ast = parser.parse(code, {
                sourceType: 'unambiguous',
                plugins: ['typescript', 'jsx']
            });

            traverse(ast, {
                CallExpression(pathObj) {
                    const node = pathObj.node;

                    // --- 1. Identify Route Handlers ---
                    if (node.callee.type === 'MemberExpression') {
                        const propertyName = node.callee.property.name;
                        const methods = ['get', 'post', 'put', 'delete', 'patch', 'use'];

                        if (methods.includes(propertyName)) {
                            const args = node.arguments;
                            // Basic check for (path, handler) signature
                            if (args.length >= 2) {
                                let routePath = '/';
                                if (args[0].type === 'StringLiteral') {
                                    routePath = args[0].value;
                                } else if (args[0].type === 'TemplateLiteral') {
                                    routePath = args[0].quasis.map(q => q.value.raw).join('{param}');
                                } else {
                                    // If path is not the first arg (e.g. middleware use), skip logic for now or handle differently
                                }

                                // Handlers are usually functions
                                const handler = args.find(arg =>
                                    arg.type === 'ArrowFunctionExpression' ||
                                    arg.type === 'FunctionExpression'
                                );

                                if (handler && handler.body) {
                                    const analysisResult = analyzeHandler(handler.body, rules);

                                    routes.push({
                                        file: path.relative(targetDir, filePath), // relative path for UI
                                        useRelativePath: true,
                                        line: node.loc.start.line,
                                        method: propertyName.toUpperCase(),
                                        path: routePath,
                                        type: 'express',
                                        framework: 'express',
                                        params: Array.from(analysisResult.params),
                                        sinks: analysisResult.sinks, // Sinks now contain flowPath
                                        sanitizers: analysisResult.sanitizers,
                                        riskLevel: analysisResult.sinks.length > 0 ? 'critical' : 'low'
                                    });
                                }
                            }
                        }
                    }
                }
            });
        }
        // --- Python Analysis (Regex) ---
        else if (ext === '.py') {
            const lines = code.split('\n');
            let currentRoute = null;

            lines.forEach((line, index) => {
                const trimmed = line.trim();
                // Match @app.route('/path', methods=['GET', 'POST']) or @APP.route...
                // Regex: @(variable).route( ... )
                const routeMatch = trimmed.match(/@[\w]+\.route\s*\(\s*['"]([^'"]+)['"](?:,\s*methods\s*=\s*\[(.*?)\])?/);

                if (routeMatch) {
                    const routePath = routeMatch[1];
                    let methods = ['GET']; // Default

                    if (routeMatch[2]) {
                        methods = routeMatch[2].replace(/['"\s]/g, '').split(',');
                    }

                    // Analyze subsequent lines for params/sinks (Very Basic Heuristic)
                    // We just scan the function body for keywords until next decorator or unindented definition
                    let cursor = index + 1;
                    const params = new Set();
                    const sinks = [];

                    while (cursor < lines.length) {
                        const nextLine = lines[cursor];
                        // Break on next definition
                        if (nextLine.match(/^@/) || nextLine.match(/^def\s/)) {
                            if (cursor > index + 2) break; // Allow def immediately after decorator
                        }

                        // Python Params Heuristics
                        if (nextLine.includes('request.args.get')) params.add('query.' + extractPyParam(nextLine, 'request.args.get'));
                        if (nextLine.includes('request.form.get')) params.add('body.' + extractPyParam(nextLine, 'request.form.get'));
                        if (nextLine.includes('request.cookies.get')) {
                            const paramName = extractPyParam(nextLine, 'request.cookies.get');
                            params.add('cookie.' + paramName);

                            // [New Rule] Check if cookie is used for logic (Broken Access Control)
                            // If accessing cookie directly without verify/session
                            sinks.push({
                                type: 'InsecureAuth',
                                detail: `Trusting Raw Cookie ('${paramName}'). Possible manipulation.`,
                                flowPath: [`[Python] request.cookies.get('${paramName}')`]
                            });
                        }

                        // Python Sinks Heuristics
                        if (nextLine.includes('eval(')) sinks.push({ type: 'RCE', detail: 'eval() detected', flowPath: ['[Python] eval() call'] });
                        if (nextLine.includes('exec(')) sinks.push({ type: 'RCE', detail: 'exec() detected', flowPath: ['[Python] exec() call'] });
                        if (nextLine.includes('subprocess.call') || nextLine.includes('os.system')) sinks.push({ type: 'RCE', detail: 'System command execution', flowPath: ['[Python] os/subprocess'] });
                        if (nextLine.includes('render_template_string')) sinks.push({ type: 'SSTI', detail: 'Possible SSTI (render_template_string)', flowPath: ['[Python] unsafe template render'] });

                        // [New Rule] Path Traversal / LFI
                        if (nextLine.match(/open\s*\(/)) {
                            sinks.push({
                                type: 'PathTraversal',
                                detail: 'File Open detected. Verify filename source.',
                                flowPath: ['[Python] open() call']
                            });
                        }

                        // [New Rule] Misconfiguration (Flask Debug Mode)
                        if (nextLine.match(/run\s*\(.*debug\s*=\s*True/)) {
                            sinks.push({
                                type: 'Misconfiguration',
                                detail: 'Flask Debug Mode enabled. RCE via Werkzeug Debugger.',
                                flowPath: ['[Config] app.run(debug=True)']
                            });
                        }

                        cursor++;
                    }

                    methods.forEach(method => {
                        routes.push({
                            file: path.relative(targetDir, filePath),
                            useRelativePath: true,
                            line: index + 1,
                            method: method.toUpperCase(),
                            path: routePath,
                            type: 'flask',
                            framework: 'flask',
                            params: Array.from(params),
                            sinks: sinks,
                            sanitizers: [],
                            riskLevel: sinks.length > 0 ? 'critical' : 'low'
                        });
                    });
                }
            });
        }
        // --- HTML / Text Analysis (Regex for Comments) ---
        else if (['.html', '.htm', '.xml'].includes(ext)) {
            const lines = code.split('\n');

            lines.forEach((line, index) => {
                // Check for HTML comments <!-- ... -->
                const commentMatch = line.match(/<!--(.*?)-->/);
                if (commentMatch) {
                    const commentContent = commentMatch[1];
                    // Check for flags or keywords (Simple Heuristic for CTF)
                    if (commentContent.includes('DH{') || /DH\{[a-f0-9]+\}/i.test(commentContent)) {
                        routes.push({
                            file: path.relative(targetDir, filePath),
                            useRelativePath: true,
                            line: index + 1,
                            method: 'INFO',
                            path: 'HTML Comment',
                            type: 'html',
                            framework: 'html',
                            params: [],
                            sinks: [{ type: 'SensitiveInfo', detail: 'CTF Flag found in HTML comment', flowPath: [`[Comment] ${commentContent.trim()}`] }],
                            sanitizers: [],
                            riskLevel: 'critical'
                        });
                    }
                }
            });
        }
        // --- HTML / Text Analysis (Regex for Comments) ---
        else if (['.html', '.htm', '.xml'].includes(ext)) {
            const lines = code.split('\n');

            lines.forEach((line, index) => {
                // Check for HTML comments <!-- ... -->
                const commentMatch = line.match(/<!--(.*?)-->/);
                if (commentMatch) {
                    const commentContent = commentMatch[1];
                    // Check for flags or keywords
                    if (commentContent.includes('DH{') || /DH\{[a-f0-9]+\}/i.test(commentContent)) {
                        routes.push({
                            file: path.relative(targetDir, filePath),
                            useRelativePath: true,
                            line: index + 1,
                            method: 'INFO',
                            path: 'HTML Comment',
                            type: 'html',
                            framework: 'html',
                            params: [],
                            sinks: [{ type: 'SensitiveInfo', detail: 'CTF Flag found in HTML comment', flowPath: [`[Comment] ${commentContent.trim()}`] }],
                            sanitizers: [],
                            riskLevel: 'critical'
                        });
                    }
                }
            });
        }

    } catch (e) {
        console.error(`Error parsing ${filePath}:`, e.message);
    }
});

function extractPyParam(line, keyword) {
    // line: username = request.cookies.get('username')
    // regex to extract 'username'
    const match = line.match(new RegExp(`${keyword.replace('.', '\\.')}\\s*\\(\\s*['"]([^'"]+)['"]`));
    return match ? match[1] : 'param';
}

// --- Core Taint Analysis Logic ---
function analyzeHandler(bodyNode, rules) {
    const params = new Set();
    const sinks = [];
    const sanitizers = []; // New collection
    const taintedVars = new Map(); // varName -> source

    // Naive 1-pass traversal for taint tracking
    traverse(bodyNode, {
        noScope: true,

        // A. Source Identification (Sources)
        MemberExpression(path) {
            const n = path.node;
            // req.body, req.query, req.params
            if (n.object.type === 'MemberExpression' && n.object.object.name === 'req') {
                if (['body', 'query', 'params'].includes(n.object.property.name)) {
                    params.add(`${n.object.property.name}.${n.property.name}`);
                }
            }
        },

        // B. Assignment Tracking (Propagation)
        VariableDeclarator(path) {
            const n = path.node;
            if (!n.init) return;

            // 1. Direct Assignment: const cmd = req.query.cmd;
            if (isTaintedSource(n.init)) {
                if (n.id.type === 'Identifier') {
                    taintedVars.set(n.id.name, getSourceName(n.init));
                }
            }
            // 2. Transitive Assignment: const final = cmd;
            else if (n.init.type === 'Identifier' && taintedVars.has(n.init.name)) {
                if (n.id.type === 'Identifier') {
                    taintedVars.set(n.id.name, taintedVars.get(n.init.name));
                }
            }
            // 3. Destructuring: const { cmd } = req.body;
            else if (n.id.type === 'ObjectPattern' && isTaintedSourceObject(n.init)) {
                n.id.properties.forEach(p => {
                    // Assuming simplified { key } pattern
                    if (p.key.type === 'Identifier') {
                        taintedVars.set(p.key.name, `req.${n.init.property.name}.${p.key.name}`);
                        params.add(`${n.init.property.name}.${p.key.name}`);
                    }
                });
            }
        },

        // C. Sink & Sanitizer Checking
        CallExpression(path) {
            const n = path.node;

            // Check against loaded rules
            rules.forEach(rule => {
                const result = rule.isSink(n); // Plugin interface isSame for simplicity
                if (result) {
                    if (rule.type === 'sanitizer') {
                        // Sanitizers don't need full taint flow path usually, just presence
                        sanitizers.push(result);
                    } else {
                        // Sinks (RCE, SQLi) need taint checking
                        const args = n.arguments;
                        let isTainted = false;
                        let flowPath = [];

                        args.forEach(arg => {
                            if (arg.type === 'Identifier' && taintedVars.has(arg.name)) {
                                isTainted = true;
                                flowPath.push(`[Source: ${taintedVars.get(arg.name)}]`);
                                flowPath.push(`[Var: ${arg.name}]`);
                            }
                            // Check for BinaryExpression (concatenation)
                            if (arg.type === 'BinaryExpression') {
                                const checkBinary = (node) => {
                                    if (node.type === 'Identifier' && taintedVars.has(node.name)) {
                                        isTainted = true;
                                        flowPath.push(`[Source: ${taintedVars.get(node.name)}]`);
                                        flowPath.push(`[Concat: ${node.name}]`);
                                    }
                                    if (node.left) checkBinary(node.left);
                                    if (node.right) checkBinary(node.right);
                                };
                                checkBinary(arg);
                            }
                        });

                        if (isTainted) {
                            flowPath.push(`[Sink: ${result.detail}]`);
                            sinks.push({ ...result, flowPath });
                        }
                        // Optional: Report untainted sinks as warnings?
                        else if (args.length > 0 && args[0].type !== 'StringLiteral') {
                            // For CTF, we might want to flag anything suspicious even if flow is broken
                            // sinks.push({ ...result, flowPath: ['[Unknown Source]'] });
                        }
                    }
                }
            });
        }
    }, bodyNode, { visitorKeys: null });

    return { params, sinks, sanitizers };
}

// Helpers
function isTaintedSource(node) {
    if (node.type === 'MemberExpression' && node.object.type === 'MemberExpression' && node.object.object.name === 'req') {
        return ['body', 'query', 'params'].includes(node.object.property.name);
    }
    return false;
}

function isTaintedSourceObject(node) {
    if (node.type === 'MemberExpression' && node.object.name === 'req') {
        return ['body', 'query', 'params'].includes(node.property.name);
    }
    return false;
}

function getSourceName(node) {
    if (node.type === 'MemberExpression') {
        // e.g. req.query.cmd
        return `${node.object.object.name}.${node.object.property.name}.${node.property.name}`;
    }
    return 'unknown';
}

console.log(JSON.stringify(routes, null, 2));
