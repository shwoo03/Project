import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function POST(req: Request) {
    try {
        const { targetDir, relativePath } = await req.json();

        if (!targetDir || !relativePath) {
            return NextResponse.json({ error: 'Missing path' }, { status: 400 });
        }

        // Security Check: Prevent LFI / Path Traversal
        const fullPath = path.resolve(targetDir, relativePath);
        if (!fullPath.startsWith(path.resolve(targetDir))) {
            return NextResponse.json({ error: 'Access denied' }, { status: 403 });
        }

        if (!fs.existsSync(fullPath)) {
            return NextResponse.json({ error: 'File not found' }, { status: 404 });
        }

        const content = fs.readFileSync(fullPath, 'utf-8');
        return NextResponse.json({ content });

    } catch (error: any) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
