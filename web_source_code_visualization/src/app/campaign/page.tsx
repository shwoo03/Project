'use client';

import React, { useEffect, useState } from 'react';
import CampaignRunner from '@/components/CampaignRunner';
import { RouteData } from '@/lib/graph-transformer';

export default function CampaignPage() {
    const [data, setData] = useState<{ routes: RouteData[], targetPath: string } | null>(null);

    useEffect(() => {
        try {
            const stored = sessionStorage.getItem('campaignData');
            if (stored) {
                setData(JSON.parse(stored));
            }
        } catch (e) {
            console.error("Failed to load campaign data", e);
        }
    }, []);

    if (!data) {
        return (
            <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-slate-500">보안 점검 데이터 로드 중...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950 text-white">
            <CampaignRunner
                routes={data.routes}
                targetPath={data.targetPath}
                onClose={() => window.close()}
            />
        </div>
    );
}
