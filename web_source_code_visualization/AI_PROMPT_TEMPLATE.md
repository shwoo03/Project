# SourceViz Auto-Detection Request

**[Usage]**
Copy this prompt when you have a local directory containing a vulnerability (e.g., a CTF problem source) and you want the AI to automatically analyze it and add detection logic to SourceViz.

---

**Prompt:**

I have a vulnerable code example located at:
`[INSERT_ABSOLUTE_PATH_HERE]`
*(Example: C:\Users\me\ctf_problems\new_exploit_case)*

**Task:**
1. **Analyze the Target**: Read the files in the provided path. Identify the specific vulnerability (e.g., RCE, Logic Error, Weak Crypto) and the code pattern causing it.
2. **Context**: Read `PROJECT_OVERVIEW.md` in the root key to understand the **SourceViz** architecture (analyze.js + rules/*.js).
3. **Implement**:
   - Create a new rule file in `scripts/rules/[vuln_name].js` that detects this specific pattern.
   - If the file type is not supported (e.g., PHP, Java) or requires special parsing, modify `scripts/analyze.js` to support it.
4. **Verify**: Ensure the new rule returns a `sink` object with `{ type, detail, flowPath }` so it appears in the dashboard.

**Goal**: Make SourceViz detect this specific vulnerability automatically.
