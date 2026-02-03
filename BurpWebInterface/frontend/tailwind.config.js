/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'burp-orange': '#ff6633',
                'burp-dark': '#1a1a2e',
                'burp-darker': '#16162a',
            },
        },
    },
    plugins: [],
}
