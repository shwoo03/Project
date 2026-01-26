
import tree_sitter_javascript
import tree_sitter_php

print("JS Dir:", dir(tree_sitter_javascript))
try:
    print("JS Language:", tree_sitter_javascript.language_javascript())
except Exception as e:
    print("JS Error:", e)

print("PHP Dir:", dir(tree_sitter_php))
try:
    print("PHP Language:", tree_sitter_php.language_php())
except Exception as e:
    print("PHP Error:", e)
