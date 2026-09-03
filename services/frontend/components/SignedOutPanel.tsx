import Link from 'next/link';
import { WorkspaceWindow } from '@/components/WorkspaceChrome';

type SignedOutPanelProps = {
  title: string;
  label: string;
  heading: string;
  description: string;
};

export default function SignedOutPanel({ title, label, heading, description }: SignedOutPanelProps) {
  return (
    <main className="mx-auto flex min-h-[calc(100vh-5.25rem)] w-full max-w-xl items-center px-5 py-16">
      <WorkspaceWindow title={title} className="w-full text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">{label}</p>
        <h1 className="mt-4 text-3xl">{heading}</h1>
        <p className="y2k-window-lead mx-auto mt-4 max-w-md">{description}</p>
        <Link href="/sign-in" className="y2k-button mt-6 inline-flex px-5 py-2.5 text-sm font-semibold">
          Sign in
        </Link>
      </WorkspaceWindow>
    </main>
  );
}
