'use client';

import Link from 'next/link';
import { authClient } from '@/lib/auth-client';
import { useEffect, useState, type ReactNode } from 'react';

type WorkspacePanelProps = {
  title: string;
  children: ReactNode;
  className?: string;
};

export function WorkspacePanel({ title, children, className = '' }: WorkspacePanelProps) {
  return (
    <section className={`workspace-panel ${className}`}>
      <div className="panel-title">
        <h2>{title}</h2>
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

type DailyUsage = {
  limit: number;
  used: number;
  remaining: number;
};

function DailyUsageMeter() {
  const [usage, setUsage] = useState<DailyUsage | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadUsage() {
      try {
        const response = await fetch('/api/usage', { credentials: 'same-origin' });
        if (!response.ok) return;
        const payload = await response.json() as Partial<DailyUsage>;
        if (
          !cancelled
          && typeof payload.limit === 'number'
          && typeof payload.used === 'number'
          && typeof payload.remaining === 'number'
        ) {
          setUsage({
            limit: payload.limit,
            used: payload.used,
            remaining: payload.remaining,
          });
        }
      } catch {
        // Keep the unavailable state if usage cannot be fetched.
      }
    }

    void loadUsage();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <p className="daily-usage">
      {usage ? `${usage.remaining} / ${usage.limit} daily requests remaining` : 'Daily usage unavailable'}
    </p>
  );
}

export function WorkspaceFrame({ crumb, children }: { crumb: ReactNode; children: ReactNode }) {
  const { data: session } = authClient.useSession();
  return (
    <main className="workspace mx-auto w-full px-5 py-6 sm:px-8 sm:py-8">
      <div className="workspace-heading">
        <div className="breadcrumb"><Link href="/">clankr</Link> / {crumb}</div>
        {session && <DailyUsageMeter key={session.user.id} />}
      </div>
      <div className="workspace-content">{children}</div>
    </main>
  );
}
