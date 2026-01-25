module.exports = {
    name: 'SensitiveComments',
    type: 'sink',

    // Keywords to look for in comments
    keywords: ['key', 'secret', 'token', 'password', 'api', 'flag', 'dh{', 'todo'],

    isSink: (node) => {
        // This rule is a bit different; it usually runs on tokens/comments scanning, 
        // but we can try to hook into String Literals or just rely on regex scan in analyze.js
        // For AST usage, we can look for template literals or strings containing specific patterns

        // In analyze.js regex fallback:
        if (typeof node === 'string') {
            const lower = node.toLowerCase();
            // DH{...} pattern
            if (node.includes('DH{') || /DH\{[a-f0-9]+\}/i.test(node)) {
                return {
                    type: 'SensitiveInfo',
                    detail: 'CTF Flag detected in content.'
                };
            }

            // Keywords
            for (const kw of module.exports.keywords) {
                if (lower.includes(kw) && node.length < 200) { // Limit length to avoid false positives in long texts
                    return {
                        type: 'SensitiveInfo',
                        detail: `Sensitive keyword '${kw}' found in text/comment.`
                    };
                }
            }
        }

        return false;
    }
};
