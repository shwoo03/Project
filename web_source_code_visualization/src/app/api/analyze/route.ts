import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import util from 'util';

const execAsync = util.promisify(exec);

export async function POST(req: Request) {
    try {
        const { targetPath, type } = await req.json();

        if (!targetPath) {
            return NextResponse.json({ error: 'Target path is required' }, { status: 400 });
        }

        const scriptsDir = path.join(process.cwd(), 'scripts');
        let command = '';

        if (type === 'flask') {
            command = `python "${path.join(scriptsDir, 'analyze.py')}" "${targetPath}"`;
        } else {
            // Default to express/node
            command = `node "${path.join(scriptsDir, 'analyze.js')}" "${targetPath}"`;
        }

        const { stdout, stderr } = await execAsync(command);

        if (stderr && stderr.trim().length > 0) {
            console.warn('Parser Query Stderr:', stderr);
        }

        const routes = JSON.parse(stdout);
        return NextResponse.json({ routes });

    } catch (error: any) {
        console.error('Analysis failed:', error);
        return NextResponse.json({ error: 'Analysis failed', details: error.message }, { status: 500 });
    }
}
