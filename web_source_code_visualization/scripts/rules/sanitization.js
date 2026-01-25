module.exports = {
    name: 'Sanitization',
    type: 'sanitizer',

    // Sanitization / Validation methods to look for
    sinks: ['replace', 'replaceAll', 'slice', 'substring', 'substr', 'split', 'match', 'test'],

    isSink: (node) => {
        if (node.type !== 'CallExpression') return false;

        // 1. String methods: str.replace(...)
        if (node.callee.type === 'MemberExpression') {
            const prop = node.callee.property.name;

            // String Replacement
            if (['replace', 'replaceAll'].includes(prop)) {
                const args = node.arguments;
                let detail = `${prop}() call`;

                // Check for weak regex or simple string replacement
                if (args.length > 0) {
                    const search = args[0];
                    if (search.type === 'StringLiteral') {
                        detail = `${prop}('${search.value}') - Simple string replace (often bypassable)`;
                    } else if (search.type === 'RegExpLiteral') {
                        const flags = search.flags || '';
                        if (!flags.includes('g')) {
                            detail = `${prop}(/${search.pattern}/) - Regex without 'g' flag (replace only first)`;
                        } else if (search.pattern.includes('script') || search.pattern.includes('alert')) {
                            detail = `${prop}(Regex) - Blacklist detection (often bypassable)`;
                        } else {
                            detail = `${prop}(Regex) - Potential sanitization`;
                        }
                    }
                }
                return { type: 'Sanitization', detail };
            }

            // String Slicing / Substring (often used for crude length checks or filters)
            if (['slice', 'substring', 'substr'].includes(prop)) {
                return { type: 'Sanitization', detail: `${prop}() - String truncation/slicing` };
            }
        }

        return false;
    }
};
