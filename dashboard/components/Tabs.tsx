'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/', label: 'Rules' },
  { href: '/agents-md', label: 'vs AGENTS.md' },
  { href: '/compare', label: 'Compare' },
  { href: '/results', label: 'Results' },
];

export function Tabs() {
  const path = usePathname();
  return (
    <nav className="tabs">
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={path === t.href ? 'page' : undefined}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
