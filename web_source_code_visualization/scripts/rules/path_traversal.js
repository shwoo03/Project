module.exports = {
    name: 'PathTraversal',
    type: 'sink',

    // Patterns for Path Traversal / LFI
    // JS: fs.readFile, fs.readFileSync, res.sendFile ...
    // Python: open(), file() -> handled in analyze.js regex

    isSink: (node) => {
        // 1. JavaScript/Express Checks (AST)
        if (node.type === 'CallExpression') {
            const callee = node.callee;

            // fs.readFile(path) or fs.readFileSync(path)
            if (callee.type === 'MemberExpression') {
                const obj = callee.object.name; // fs
                const prop = callee.property.name; // readFile, readFileSync, createReadStream

                if (obj === 'fs' && ['readFile', 'readFileSync', 'createReadStream'].includes(prop)) {
                    return {
                        type: 'PathTraversal',
                        detail: `File System Access (fs.${prop}). Verify path sanitization.`
                    };
                }

                // res.sendFile(path)
                if (obj === 'res' && prop === 'sendFile') {
                    return {
                        type: 'PathTraversal',
                        detail: `Arbitrary File Send (res.sendFile). Verify path validation.`
                    };
                }
            }
        }

        return false;
    }
};
