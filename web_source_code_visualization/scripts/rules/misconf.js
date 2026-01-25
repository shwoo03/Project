module.exports = {
    name: 'Misconfiguration',
    type: 'sink',

    isSink: (node) => {
        // 1. JS/Express: CORS origin * (AST)
        if (node.type === 'CallExpression') {
            // app.use(cors({ origin: '*' }))
            if (node.callee.name === 'cors') {
                const args = node.arguments;
                if (args.length > 0 && args[0].type === 'ObjectExpression') {
                    const originProp = args[0].properties.find(p => p.key.name === 'origin');
                    if (originProp && originProp.value.type === 'StringLiteral' && originProp.value.value === '*') {
                        return {
                            type: 'Misconfiguration',
                            detail: 'Insecure CORS (Origin: *). Allows all domains.',
                            flowPath: ['[Config] cors({ origin: "*" })']
                        };
                    }
                }
                // app.use(cors()) -> Default might be * depending on version, but explicit is worse
            }
        }

        return false;
    }
};
