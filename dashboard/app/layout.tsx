import type { Metadata } from 'next';
import './globals.css';
import { Tabs } from '@/components/Tabs';
import { getRuleBook } from '@/lib/data';

export const metadata: Metadata = {
  title: 'House Style',
  description:
    "Review conventions mined from a repository's own merged-PR history, with the evidence behind each one.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const book = getRuleBook('airflow');
  return (
    <html lang="en">
      <body>
        <header className="masthead">
          <div className="masthead-inner">
            <p className="wordmark">
              <a href="/">House Style</a>
              <span className="repo">{book.repo || 'no rulebook generated yet'}</span>
            </p>
            <p className="tagline">
              The conventions this repository&rsquo;s reviewers actually enforce, mined
              from merged pull requests. Every rule carries the reviews it came from.
            </p>
            <Tabs />
          </div>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
