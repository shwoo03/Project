const fs = require('fs');
const path = require('path');
const glob = require('glob');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

// Clean argument path for Windows
let targetDir = process.argv[2] || '.';
targetDir = targetDir.replace(/\\/g, '/'); // Normalize slashes

// Debug to stderr (visible in Next.js console)
console.error(`Analyzing directory: ${targetDir}`);

const files = glob.sync('**/*.{js,ts}', {
    cwd: targetDir,
    ignore: ['**/node_modules/**', '**/dist/**', '**/.next/**'],
    absolute: true
});

console.error(`Found ${files.length} files.`);

const routes = [];

files.forEach(filePath => {
    try {
        const code = fs.readFileSync(filePath, 'utf-8');

        // Parse as unkwown/module to allow both
        const ast = parser.parse(code, {
            sourceType: 'unambiguous',
            plugins: ['typescript', 'jsx']
        });

        traverse(ast, {
            CallExpression({ node }) {
                if (node.callee.type === 'MemberExpression') {
                    const propertyName = node.callee.property.name;
                    // const objectName = node.callee.object.name; // app or router

                    const methods = ['get', 'post', 'put', 'delete', 'patch', 'use'];

                    if (methods.includes(propertyName)) {
                        const args = node.arguments;
                        if (args.length > 0) {
                            let routePath = '/';
                            if (args[0].type === 'StringLiteral') {
                                routePath = args[0].value;
                            } else if (args[0].type === 'TemplateLiteral') {
                                routePath = args[0].quasis.map(q => q.value.raw).join('{param}');
                            } else {
                                return;
                            }

                            // --- Security Analysis Start ---
                            const params = new Set();
                            const sinks = [];
                            let hasSanitization = false;

                            // Helper to scan function body
                            const handler = args.find(arg => arg.type === 'ArrowFunctionExpression' || arg.type === 'FunctionExpression');

                            if (handler && handler.body) {
                                traverse(handler.body, {
                                    noScope: true, // Simple traversal inside handler

                                    // 1. Parameter Extraction (req.body.x, req.query.y)
                                    MemberExpression(path) {
                                        const n = path.node;
                                        if (n.object.type === 'MemberExpression' && n.object.object.name === 'req') {
                                            // req.body.username -> property.name = username
                                            if (['body', 'query', 'params'].includes(n.object.property.name)) {
                                                params.add(`${n.object.property.name}.${n.property.name}`);
                                            }
                                        }
                                        // Destructuring: const { x } = req.body
                                        if (n.object.name === 'req' && ['body', 'query', 'params'].includes(n.property.name)) {
                                            // This is harder to track without full scope analysis, identifying via VariableDeclarator below
                                        }
                                    },

                                    VariableDeclarator(path) {
                                        const n = path.node;
                                        if (n.init && n.init.type === 'MemberExpression' && n.init.object.name === 'req') {
                                            // const { x } = req.body;
                                            if (n.id.type === 'ObjectPattern') {
                                                n.id.properties.forEach(p => {
                                                    params.add(`${n.init.property.name}.${p.key.name}`);
                                                });
                                            }
                                        }
                                    },

                                    // 2. Sink Detection (Danger Patterns)
                                    CallExpression(path) {
                                        const n = path.node;
                                        const callee = n.callee;

                                        // eval(), exec()
                                        if (callee.name === 'eval') sinks.push({ type: 'RCE', detail: 'eval() detected' });

                                        // child_process.exec(cmd)
                                        if (callee.property && ['exec', 'spawn'].includes(callee.property.name)) {
                                            sinks.push({ type: 'RCE', detail: 'Process execution detected' });
                                        }

                                        // db.query(), pool.execute() - Naive SQL heuristic
                                        if (callee.property && ['query', 'execute'].includes(callee.property.name)) {
                                            // Check arguments for string concatenation
                                            const queryArg = n.arguments[0];
                                            if (queryArg && queryArg.type === 'BinaryExpression' && queryArg.operator === '+') {
                                                sinks.push({ type: 'SQLi', detail: 'Potential SQL Injection (String concat)' });
                                            }
                                        }
                                    }
                                }, handler, { visitorKeys: null }); // Need correct visitor context or manual recursion? 
                                // Babel traverse inside traverse can be tricky. Using manual AST walk or scope-less traverse is safer for simple scripts.
                                // Re-implementing simple recursive walk for the handler body to avoid scope issues.
                            }
                            // --- Security Analysis End ---

                            routes.push({
                                file: path.relative(targetDir, filePath),
                                useRelativePath: true, // marker
                                line: node.loc.start.line,
                                method: propertyName.toUpperCase(),
                                path: routePath,
                                type: 'express',
                                framework: 'express',
                                params: Array.from(params),
                                sinks: sinks,
                                riskLevel: sinks.length > 0 ? 'critical' : 'low'
                            });
                        }
                    }
                }
            }
        });
    } catch (e) {
        console.error(`Error parsing ${filePath}:`, e.message);
    }
});

console.log(JSON.stringify(routes, null, 2));
