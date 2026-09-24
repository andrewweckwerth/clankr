'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import AuthControls from '@/components/AuthControls';

const NAVIGATION = [
  ['/projects/new', 'Pipeline'],
  ['/jobs', 'Jobs'],
  ['/tools', 'Tools'],
  ['/songs', 'Songs'],
];

export default function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="site-header">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4 sm:px-8">
        <Link href="/" className="text-lg font-semibold tracking-tight" aria-label="Clankr home">clankr</Link>
        <nav aria-label="Main navigation" className="site-nav order-3 sm:order-none">
          {NAVIGATION.map(([href, label]) => (
            <Link key={href} href={href} aria-current={pathname.startsWith(href) || (href === '/projects/new' && pathname === '/') ? 'page' : undefined}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto"><AuthControls /></div>
      </div>
    </header>
  );
}
