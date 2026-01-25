import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import util from 'util';
import fs from 'fs';
import path from 'path';

const execAsync = util.promisify(exec);

export async function POST(req: Request) {
    try {
        const { targetPath, action } = await req.json(); // action: 'check', 'start', 'stop'

        if (!targetPath) {
            return NextResponse.json({ error: 'Target path required' }, { status: 400 });
        }

        const hasCompose = fs.existsSync(path.join(targetPath, 'docker-compose.yml')) ||
            fs.existsSync(path.join(targetPath, 'docker-compose.yaml'));
        const hasDockerfile = fs.existsSync(path.join(targetPath, 'Dockerfile'));

        if (action === 'check') {
            return NextResponse.json({
                canDeploy: hasCompose || hasDockerfile,
                type: hasCompose ? 'compose' : (hasDockerfile ? 'dockerfile' : 'none')
            });
        }

        if (action === 'start') {
            if (hasCompose) {
                // Run docker-compose
                await execAsync(`docker-compose up -d --build`, { cwd: targetPath });
                return NextResponse.json({ message: 'Docker Compose started successfully.' });
            } else if (hasDockerfile) {
                // Build and run simple container
                const imageName = 'sourceviz-target';
                await execAsync(`docker build -t ${imageName} .`, { cwd: targetPath });
                // Stop prev container if exists
                try { await execAsync(`docker rm -f ${imageName}-inst`); } catch { }
                // Run on random port or 8080? Let's fix to 1337 for CTF convention or find free port.
                // For simplicity MVP: Map 80 to 80 or 8000 to 8000.
                await execAsync(`docker run -d -p 8000:8000 --name ${imageName}-inst ${imageName}`);
                return NextResponse.json({ message: 'Dockerfile built and deployed on port 8000.' });
            } else {
                return NextResponse.json({ error: 'No Docker configuration found.' }, { status: 404 });
            }
        }

        if (action === 'stop') {
            if (hasCompose) {
                await execAsync(`docker-compose down`, { cwd: targetPath });
            } else {
                try { await execAsync(`docker rm -f sourceviz-target-inst`); } catch { }
            }
            return NextResponse.json({ message: 'Environment stopped.' });
        }

        return NextResponse.json({ error: 'Invalid action' }, { status: 400 });

    } catch (error: any) {
        console.error('Docker Error:', error);
        return NextResponse.json({
            error: error.message || 'Docker operation failed. Ensure Docker Desktop is running.'
        }, { status: 500 });
    }
}
