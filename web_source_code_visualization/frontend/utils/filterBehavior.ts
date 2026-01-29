// ============================================
// Filter Behavior Analysis Utilities
// ============================================

interface FilterBehaviorResult {
    behavior: string;
    examples: string;
}

/**
 * Extract named argument from argument list
 * e.g. getNamedArg(['arg1', 'safe=/'], 'safe') => '/'
 */
export function getNamedArg(args: string[] | undefined, name: string): string | null {
    if (!args || args.length === 0) return null;
    const match = args.find((arg) => arg.trim().startsWith(`${name}=`));
    if (!match) return null;
    const parts = match.split("=");
    return parts.slice(1).join("=").trim() || null;
}

/**
 * Describe the filtering/encoding behavior of known sanitizer functions
 */
export function describeFilterBehavior(name: string, args: string[] | undefined): FilterBehaviorResult {
    const lower = name.toLowerCase();

    // URL Encoding
    if (lower === 'urllib.parse.quote' || lower === 'urllib.parse.quote_plus') {
        const safeArg = getNamedArg(args, 'safe') || (args && args.length > 1 ? args[1] : null);
        const safeLabel = safeArg ? `safe=${safeArg}` : "safe='/'";
        const behaviorBase = lower.endsWith('quote_plus')
            ? 'URL-encode (space -> +)'
            : 'URL-encode';
        return {
            behavior: `${behaviorBase}; leaves ${safeLabel} unescaped`,
            examples: "space, '\"', <, >, #, ?, &, %, +, ="
        };
    }

    // HTML Escaping
    if (lower === 'html.escape' || lower === 'markupsafe.escape' || lower === 'flask.escape' || lower === 'werkzeug.utils.escape' || lower === 'cgi.escape') {
        const quoteArg = getNamedArg(args, 'quote');
        const quotesEscaped = !quoteArg || !/false/i.test(quoteArg);
        return {
            behavior: 'HTML escape',
            examples: quotesEscaped ? '&, <, >, ", \'' : '&, <, >'
        };
    }

    // Bleach Library
    if (lower === 'bleach.clean') {
        return {
            behavior: 'Strip/clean HTML tags and attributes',
            examples: '<script>, onclick='
        };
    }

    // Generic escape/sanitize patterns
    if (lower.endsWith('.escape') || lower.endsWith('.sanitize') || lower === 'escape' || lower === 'sanitize') {
        return {
            behavior: 'Custom sanitizer (unknown behavior)',
            examples: 'inspect function body'
        };
    }

    return {
        behavior: 'Unknown sanitizer',
        examples: '-'
    };
}

/**
 * Format parameter type for display
 */
export function formatParamType(param: { source?: string; type?: string } | null | undefined): string {
    if (param?.source && ['path', 'query', 'body', 'header', 'cookie'].includes(param.source)) {
        switch (param.source) {
            case 'path':
                return 'Path Param';
            case 'query':
                return 'Query';
            case 'body':
                return 'Body';
            case 'header':
                return 'Header';
            case 'cookie':
                return 'Cookie';
        }
    }
    return param?.type || 'Unknown';
}
