# Vulnerability Search Patterns

## Remote Code Execution (RCE)
### Node.js
- `child_process.exec(`
- `child_process.spawn(`
- `eval(`
- `new Function(`
- `vm.runInContext(`
- `setTimeout(` (with string arg)
- `setInterval(` (with string arg)

### Python
- `subprocess.call(`
- `subprocess.Popen(`
- `os.system(`
- `os.popen(`
- `eval(`
- `exec(`
- `pickle.loads(`
- `yaml.load(` (unsafe loader)

### PHP
- `system(`
- `exec(`
- `passthru(`
- `shell_exec(`
- `eval(`
- `assert(`
- `backticks` (e.g. \`ls\`)
- `preg_replace` (with /e modifier)

### Java
- `Runtime.getRuntime().exec(`
- `ProcessBuilder`
- `ScriptEngine.eval`

## SQL Injection
### General
- `SELECT * FROM` (concatenated string)
- `INSERT INTO` (concatenated string)
- `UPDATE` (concatenated string)
- `DELETE FROM` (concatenated string)
- Raw queries in ORMs (e.g., `sequelize.query`, `User.raw`, `execute_sql`)

## SSRF
- `fetch(` (with user input)
- `axios.get(` (with user input)
- `request(`
- `http.get(`
- `curl_exec(`
- `urllib.urlopen(`

## Broken Authentication / Access Control
- `verifyToken` (check usually weak implementation)
- `jwt.verify` (missing `algorithms` check, `none` algo)
- `req.user.id` vs `req.params.id` (IDOR check)
- `role` checks in frontend only
- `password` in logs

## File Upload / Path Traversal
- `req.files`
- `fs.readFile(` (with user input)
- `fs.createReadStream(`
- `path.join(` (check for `../`)
- Zip extraction (SlipZip/ZipSlip)

## Secrets
- `aws_access_key`
- `api_key`
- `private_key`
- `password` (hardcoded)
- `.env` files committed
