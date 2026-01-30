'use client';

import dynamic from 'next/dynamic';

const Visualizer = dynamic(() => import('./Visualizer'), {
    ssr: false,
});

export default function VisualizerWrapper() {
    return <Visualizer />;
}
