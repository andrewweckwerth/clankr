'use client';

import { authClient } from '@/lib/auth-client';
import Link from 'next/link';
import { useEffect, useState, type ReactNode } from 'react';

type WorkspaceWindowProps = {
  title: string;
  children: ReactNode;
  className?: string;
};

export function WorkspaceWindow({ title, children, className = '' }: WorkspaceWindowProps) {
  return (
    <section className={`y2k-window ${className}`}>
      <div className="y2k-window-title">
        <span><span className="y2k-window-icon" aria-hidden="true">✦</span> {title}</span>
      </div>
      <div className="y2k-window-body">{children}</div>
    </section>
  );
}

type DailyUsage = {
  limit: number;
  used: number;
  remaining: number;
};

const DEFAULT_DAILY_LIMIT = 10;

function DailyUsageMeter() {
  const [usage, setUsage] = useState<DailyUsage | null>(null);
  const limit = usage?.limit ?? DEFAULT_DAILY_LIMIT;
  const remaining = Math.max(0, Math.min(usage?.remaining ?? limit, limit));
  const used = Math.max(0, Math.min(usage?.used ?? 0, limit));

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
        // The server remains the source of truth for the limit; keep the default display if it is unavailable.
      }
    }

    void loadUsage();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="y2k-profile-usage" aria-label={`${remaining} of ${limit} daily requests available`}>
      <div className="y2k-profile-usage-label">
        <span>Daily requests</span>
        <strong>{remaining} of {limit} available</strong>
      </div>
      <div
        className="y2k-usage-meter"
        role="progressbar"
        aria-label="Daily requests available"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={remaining}
      >
        {Array.from({ length: limit }, (_, index) => (
          <span key={index} className={index < remaining ? 'is-available' : 'is-used'} />
        ))}
      </div>
      <p>{used} used today · {limit} requests per day</p>
    </section>
  );
}

export function WorkspaceSidebar() {
  const { data: session } = authClient.useSession();
  const name = session?.user.name || 'Your';
  const email = session?.user.email || 'Audio workspace';

  return (
    <aside className="y2k-workspace-sidebar">
      <WorkspaceWindow title={`${name}'s Workspace`}>
        <div className="y2k-profile">
          <div className="y2k-profile-avatar" aria-hidden="true">c</div>
          <h1>{name}</h1>
          <p>{email}</p>
          <DailyUsageMeter />
        </div>
      </WorkspaceWindow>

      <WorkspaceWindow title="Quick Links">
        <ul className="y2k-shortcut-list">
          <li><Link className="y2k-button" href="/projects/new">Full Pipeline</Link></li>
          <li><Link className="y2k-button" href="/tools">Standalone Tools</Link></li>
          <li><Link className="y2k-button" href="/jobs">My Jobs</Link></li>
          <li><Link className="y2k-button" href="/songs">My Songs</Link></li>
          <li><Link className="y2k-button" href="/songs?view=all">All Songs</Link></li>
          <li><Link className="y2k-button" href="/account">Account Settings</Link></li>
        </ul>
      </WorkspaceWindow>

      <WorkspaceWindow title="Clankr Info">
        <div className="y2k-sidebar-info">
          <p>Analyze recordings and assess lyrics for AI generation.</p>
          <a href="mailto:andrew.weckwerth@outlook.com">andrew.weckwerth@outlook.com</a>
          <small>© 2026 Clankr</small>
        </div>
      </WorkspaceWindow>
    </aside>
  );
}

export function WorkspaceFrame({ crumb, children }: { crumb: ReactNode; children: ReactNode }) {
  return (
    <main className="y2k-workspace y2k-workspace-frame mx-auto min-h-[calc(100vh-11rem)] w-full px-5 py-6 sm:px-8 sm:py-8">
      <div className="y2k-breadcrumb"><Link href="/">Home</Link> &gt; {crumb}</div>
      <div className="y2k-workspace-grid">
        <WorkspaceSidebar />
        <section className="y2k-workspace-main y2k-frame-content">{children}</section>
      </div>
    </main>
  );
}
