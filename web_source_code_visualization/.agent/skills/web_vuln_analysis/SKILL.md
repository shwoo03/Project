---
name: web-vuln-analysis
description: Guide for analyzing web open source codebase for high-impact vulnerabilities (RCE, SQLi, SSRF, IDOR, etc.). Use this when the task is to audit code for security flaws or find bugs for bug bounties.
---

# Web Vulnerability Analysis Skill

This skill guides the identification of **realistic, high-impact** security vulnerabilities in web applications. It focuses on issues typically accepted in Bug Bounty programs (P1/P2) and strictly avoids low-impact "spam" issues.

## 🚫 Out of Scope (Do Not Report)
- Missing HTTP Headers (X-Frame-Options, HSTS, CSP, etc.)
- Cookie Flags (Missing HttpOnly/Secure)
- Self-XSS / Logout CSRF
- Generic DoS (unless logic-based and critical)
- DNS Rebinding (unless specific context exists)
- Banner Grabbing / Version Disclosure
- SSL/TLS Configuration Weaknesses

## 🎯 In Scope (Focus Areas)
1. **Remote Code Execution (RCE)**
   - Unsafe command execution, unsafe deserialization, code injection.
2. **Injection**
   - SQL Injection (especially in raw queries), NoSQL Injection.
3. **Broken Authentication & Session Management**
   - Auth bypass, Token leakage, Weak logic, JWT issues (None algo).
4. **Broken Access Control (IDOR)**
   - Accessing objects of other users (manipulating IDs).
   - Privilege Escalation (User -> Admin).
5. **Server-Side Request Forgery (SSRF)**
   - Accessing internal metadata or internal services.
6. **Insecure Direct Object References (IDOR)**
7. **Mass Assignment / Prototype Pollution**
8. **Sensitive Data Exposure**
   - Hardcoded secrets, keys, PII leakage.

## 🕵️ Analysis Workflow

### Step 1: Technology Recognition
Identify the core stack:
- **Backend**: Node.js, Python/Django/Flask, PHP/Laravel, Go, Java/Spring?
- **Database**: SQL (Postgres/MySQL), NoSQL (Mongo/Redis)?
- **Auth**: JWT, Session, OAuth?

### Step 2: Dangerous Pattern Search
Search for known dangerous functions and patterns.
Use the patterns defined in [patterns.md](references/patterns.md) as a starting point.

**Action**: Use `grep_search` to find occurrences of these patterns.

### Step 3: Source-to-Sink Analysis
For each potential match found in Step 2:
1. **Identify the Sink**: The dangerous function being called (e.g., `exec()`, `query()`).
2. **Trace the Source**: Where does the data come from?
   - `req.body`, `req.query`, `req.params`?
   - Database read?
   - External API response?
3. **Verify Sanitization**: Is the data sanitized or validated before reaching the sink?
   - Are parameterized queries used?
   - Is there input validation (e.g., regex whitelist)?

### Step 4: Logic Analysis (Manual Review)
Beyond grep-able patterns, look for logic flaws:
- **Auth Middleware**: Check if every protected route *actually* applies the middleware.
- **ID Checks**: In endpoints like `GET /user/:id/data`, does it verify if `current_user.id == :id`?
- **Business Logic**: obscure flows like "Apply Coupon", "Transfer Funds", "Reset Password".

## 📝 Reporting
When a vulnerability is found, document it with:
1. **Vulnerability Type**
2. **Impact**: Why is this bad? (e.g., "Attacker can read any user's email")
3. **Location**: File and Line Number.
4. **Proof of Concept (Mental or Script)**: Describe how the input flows to the dangerous sink.
