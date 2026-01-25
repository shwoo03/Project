const express = require('express');
const app = express();

// User routes
app.get('/api/users', (req, res) => {
    res.json({ users: [] });
});

app.post('/api/users', (req, res) => {
    res.status(201).send('Created');
});

app.put('/api/users/:id', (req, res) => {
    res.send('Updated');
});

app.delete('/api/users/:id', (req, res) => {
    res.send('Deleted');
});

// Auth routes (unprotected for demo)
app.post('/auth/login', (req, res) => {
    const { username, password } = req.body; // Params extraction test
    res.send('Token');
});

// Vulnerable RCE Endpoint (Variable Propagation Test)
app.get('/admin/system-diag', (req, res) => {
    const userCmd = req.query.cmd; // Source
    const finalCmd = userCmd;      // Propagation
    require('child_process').exec(finalCmd); // Sink
    res.send('Executed');
});

// Vulnerable SQL Injection Endpoint
app.post('/api/search', (req, res) => {
    const query = req.body.q;
    // Simulated SQLi with inline concatenation (easier for simple parser to catch)
    db.query("SELECT * FROM items WHERE name = '" + query + "'");
    res.send('Results');
});

// Router example
const adminRouter = express.Router();
adminRouter.get('/dashboard', (req, res) => {
    res.send('Admin Dashboard');
});
adminRouter.post('/ban-user', (req, res) => {
    // Weak sanitizer test
    let input = req.body.user;
    input = input.replace('script', ''); // Weak sanitizer
    res.send(`Banned ${input}`);
});

app.use('/admin', adminRouter);

app.listen(3000, () => console.log('Server running'));
