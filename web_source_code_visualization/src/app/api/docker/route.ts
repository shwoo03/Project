import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import util from 'util';
import fs from 'fs';
import path from 'path';

const execAsync = util.promisify(exec);

// Simple in-memory store for logs and child processes (MVP)
// In a real app, use a proper process manager or database
let activeChild: any = null;
let processLogs: string[] = [];

export async function POST(req: Request) {
    try {
        const { targetPath, action } = await req.json(); // action: 'check', 'start', 'stop', 'logs'

        if (action === 'logs') {
            return NextResponse.json({ logs: processLogs });
        }

        if (!targetPath) {
            return NextResponse.json({ error: 'Target path required' }, { status: 400 });
        }

        const hasCompose = fs.existsSync(path.join(targetPath, 'docker-compose.yml')) ||
            fs.existsSync(path.join(targetPath, 'docker-compose.yaml'));
        const hasDockerfile = fs.existsSync(path.join(targetPath, 'Dockerfile'));
        const hasAppPy = fs.existsSync(path.join(targetPath, 'app.py'));

        if (action === 'check') {
            return NextResponse.json({
                canDeploy: hasCompose || hasDockerfile || hasAppPy,
                type: hasCompose ? 'compose' : (hasDockerfile ? 'dockerfile' : (hasAppPy ? 'python' : 'none'))
            });
        }

        if (action === 'start') {
            // Reset logs on new start
            processLogs = [];
            processLogs.push('--- Starting Deployment ---');

            if (hasCompose) {
                // Run docker-compose
                await execAsync(`docker-compose up -d --build`, { cwd: targetPath });
                processLogs.push('Docker Compose started.');
                return NextResponse.json({ message: 'Docker Compose started successfully.' });
            } else if (hasDockerfile) {
                // Build and run simple container
                const imageName = 'sourceviz-target';
                await execAsync(`docker build -t ${imageName} .`, { cwd: targetPath });
                try { await execAsync(`docker rm -f ${imageName}-inst`); } catch { }
                await execAsync(`docker run -d -p 8000:8000 --name ${imageName}-inst ${imageName}`);
                processLogs.push('Dockerfile deployed on port 8000.');
                return NextResponse.json({ message: 'Dockerfile built and deployed on port 8000.' });
            } else {
                // FALLBACK: Direct Execution (No Docker)
                // Check for app.py or package.json
                if (hasAppPy) {
                    if (activeChild) {
                        try { process.kill(activeChild.pid); } catch { }
                    }

                    // Spawn Python Process
                    const { spawn } = require('child_process');
                    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

                    activeChild = spawn(pythonCmd, ['app.py'], { cwd: targetPath, shell: true });

                    processLogs.push(`Spawned process PID: ${activeChild.pid}`);

                    activeChild.stdout.on('data', (data: any) => {
                        processLogs.push(data.toString().trim());
                    });

                    activeChild.stderr.on('data', (data: any) => {
                        const str = data.toString().trim();
                        // Flask/Werkzeug prints info to stderr. Don't mark as error.
                        if (str.includes('Running on') || str.includes('Debugger active') || str.includes('Debug mode')) {
                            processLogs.push(`[INFO] ${str}`);
                        } else {
                            processLogs.push(`[ERR] ${str}`);
                        }
                    });

                    activeChild.on('close', (code: any) => {
                        processLogs.push(`Process exited with code ${code}`);
                        activeChild = null;
                    });

                    return NextResponse.json({ message: 'Python app started DIRECTLY. Logs capturing...' });
                }

                return NextResponse.json({ error: 'No Dockerfile or app.py found.' }, { status: 404 });
            }
        }

        if (action === 'stop') {
            if (activeChild) {
                try { process.kill(activeChild.pid); } catch { }
                activeChild = null;
                processLogs.push('Process stopped by user.');
            }
            // Cleanup Docker as well just in case
            if (hasCompose) try { await execAsync(`docker-compose down`, { cwd: targetPath }); } catch { }
            else try { await execAsync(`docker rm -f sourceviz-target-inst`); } catch { }

            // Cleanup global python
            try { await execAsync(`taskkill /F /IM python.exe`); } catch { }

            return NextResponse.json({ message: 'Environment stopped.' });
        }

        return NextResponse.json({ error: 'Invalid action' }, { status: 400 });

    } catch (error: any) {
        console.error('Docker Error:', error);
        processLogs.push(`[SYSTEM ERROR] ${error.message}`);
        return NextResponse.json({
            error: error.message || 'Operation failed.'
        }, { status: 500 });
    }
}
