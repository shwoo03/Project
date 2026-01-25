module.exports = {
    name: 'RCE',
    type: 'sink',
    // Sinks we are looking for
    sinks: ['eval', 'exec', 'spawn', 'execSync', 'spawnSync'],

    // Check function to verify if a node is a matching sink
    isSink: (node) => {
        if (node.type !== 'CallExpression') return false;

        const callee = node.callee;

        // Check for direct calls: eval()
        if (callee.type === 'Identifier' && callee.name === 'eval') {
            return { type: 'RCE', detail: 'eval() detected' };
        }

        // Check for method calls: child_process.exec() or exec() imports
        if (callee.type === 'MemberExpression') {
            const prop = callee.property.name;
            if (['exec', 'spawn', 'execSync', 'spawnSync'].includes(prop)) {
                return { type: 'RCE', detail: `Process execution (${prop}) detected` };
            }
        }

        return false;
    }
};
