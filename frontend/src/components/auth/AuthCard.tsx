import type { ReactNode } from 'react';

export default function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <p className="mb-6 text-center text-sm font-semibold tracking-tight text-indigo-600">
          Knowledge Map
        </p>
        <div className="rounded-lg border border-neutral-200 bg-white p-6">
          <h1 className="mb-4 text-base font-semibold text-neutral-900">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  );
}
