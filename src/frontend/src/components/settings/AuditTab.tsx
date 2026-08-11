import { useState } from 'react';
import type { Workspace } from '../../api/types';
import { useAudit } from '../../hooks/queries';
import { formatDateTime } from '../../lib/utils';
import { Button, EmptyState, ErrorNote, Spinner } from '../ui/primitives';

const PAGE_SIZE = 20;

function describeDetail(detail: Record<string, unknown> | null): string {
  if (!detail) return '—';
  return Object.entries(detail)
    .map(([key, value]) => {
      const rendered = typeof value === 'string' ? value : JSON.stringify(value);
      return `${key}: ${rendered}`;
    })
    .join(' · ');
}

export default function AuditTab({ workspace }: { workspace: Workspace }) {
  const [page, setPage] = useState(1);
  const auditQ = useAudit(workspace.id, page);

  if (auditQ.isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (auditQ.isError) {
    return <ErrorNote message="Failed to load the audit log (admin access required)." />;
  }

  const items = auditQ.data?.items ?? [];
  const total = auditQ.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[13px] text-neutral-700">Workspace activity history</p>
          <p className="mt-0.5 text-xs text-neutral-400">
            {total} entries · {PAGE_SIZE} per page
          </p>
        </div>
        {auditQ.isFetching && <Spinner className="h-4 w-4" />}
      </div>

      {items.length === 0 ? (
        <EmptyState message="No audit entries yet." />
      ) : (
        <div className="overflow-x-auto rounded-md border border-neutral-200 bg-surface">
          <table className="w-full min-w-[820px] table-fixed text-left">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-[11px] uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="w-40 px-3 py-2 font-medium">Time</th>
                <th className="w-32 px-3 py-2 font-medium">Actor</th>
                <th className="w-44 px-3 py-2 font-medium">Action</th>
                <th className="w-48 px-3 py-2 font-medium">Target</th>
                <th className="px-3 py-2 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 text-xs text-neutral-700">
              {items.map((item) => {
                const detail = describeDetail(item.detail);
                return (
                  <tr key={item.id} className="align-top hover:bg-neutral-50/70">
                    <td className="whitespace-nowrap px-3 py-2.5 text-neutral-500">
                      {formatDateTime(item.created_at)}
                    </td>
                    <td className="truncate px-3 py-2.5 font-medium text-neutral-800">
                      {item.actor?.name ?? 'System'}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[11px] text-neutral-600">
                        {item.action}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <p className="truncate font-medium text-neutral-800">
                        {item.target_title ?? item.target_id ?? '—'}
                      </p>
                      <p className="mt-0.5 text-[11px] text-neutral-400">{item.target_type}</p>
                    </td>
                    <td className="break-words px-3 py-2.5 text-neutral-500" title={detail}>
                      {detail}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between">
          <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            Previous
          </Button>
          <span className="text-xs text-neutral-500">
            Page {page} of {totalPages}
          </span>
          <Button
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
