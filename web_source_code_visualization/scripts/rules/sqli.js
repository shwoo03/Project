module.exports = {
    name: 'SQLi',
    type: 'sink',
    sinks: ['query', 'execute'],

    isSink: (node) => {
        if (node.type !== 'CallExpression') return false;

        const callee = node.callee;

        // Check for method calls: db.query(), pool.execute()
        if (callee.type === 'MemberExpression') {
            const prop = callee.property.name;
            if (['query', 'execute'].includes(prop)) {
                // Simple Heuristic: Check if first argument involves binary expression with '+'
                // This usually indicates string concatenation: "SELECT * FROM users WHERE name = " + input
                const args = node.arguments;
                if (args.length > 0 && args[0].type === 'BinaryExpression' && args[0].operator === '+') {
                    return { type: 'SQLi', detail: 'Potential SQL Injection (String concat)' };
                }
            }
        }

        return false;
    }
};
