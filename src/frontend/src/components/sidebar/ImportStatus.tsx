import { AlertTriangle, Loader2 } from 'lucide-react';
import type { ImportProgress, ImportResult } from '../../lib/importMd';
import { importSummary } from '../../lib/importMd';

export default function ImportStatus({
  progress,
  result,
}: {
  progress: ImportProgress | null;
  result: ImportResult | null;
}) {
  if (!progress && !result) return null;
  const current = progress?.result ?? result;
  const hasProblems = Boolean(current && (current.failed > 0 || current.warnings.length > 0));
  const percent = progress?.total
    ? Math.round((progress.completed / progress.total) * 100)
    : progress
      ? 0
      : 100;

  return (
    <div
      className={`mb-1 rounded-md border px-2 py-1.5 text-[11px] ${
        hasProblems
          ? 'border-amber-200 bg-amber-50 text-amber-800'
          : 'border-indigo-100 bg-indigo-50 text-indigo-700'
      }`}
      role={hasProblems ? 'alert' : 'status'}
    >
      <div className="flex items-center gap-1.5">
        {progress ? (
          <Loader2 size={12} className="flex-none animate-spin" />
        ) : hasProblems ? (
          <AlertTriangle size={12} className="flex-none" />
        ) : null}
        <span className="min-w-0 flex-1 truncate">
          {progress
            ? `Importing ${progress.completed}/${progress.total}: ${progress.current || 'Preparing…'}`
            : current
              ? `Import complete: ${importSummary(current)}`
              : ''}
        </span>
        <span className="tabular-nums">{percent}%</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded bg-black/10">
        <div className="h-full bg-current transition-[width]" style={{ width: `${percent}%` }} />
      </div>
      {current && (progress || hasProblems) && (
        <p className="mt-1">{importSummary(current)}</p>
      )}
      {!progress && current?.warnings.length ? (
        <details className="mt-1">
          <summary className="cursor-pointer">Show warnings</summary>
          <ul className="mt-1 max-h-28 list-disc overflow-y-auto pl-4">
            {current.warnings.slice(0, 20).map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
