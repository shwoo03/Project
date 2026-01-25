module.exports = {
    name: 'InsecureAuth',
    type: 'sink',

    // Patterns related to weak authentication
    sinks: ['cookies', 'cookie', 'set_cookie'],

    isSink: (node) => {
        // 1. JavaScript/Express: req.cookies usage for auth
        if (node.type === 'MemberExpression') {
            // req.cookies.username
            if (node.object.type === 'MemberExpression' && node.object.property.name === 'cookies') {
                return {
                    type: 'InsecureAuth',
                    detail: 'Unsigned Cookie Access (req.cookies). Verify if used for Auth.'
                };
            }
        }

        // 2. Python/Flask Pattern (handled via Analyze.js regex mostly, but logic here for JS/TS)
        // Checking for simple logic like: if (req.cookies.user === 'admin')

        return false;
    }
};
