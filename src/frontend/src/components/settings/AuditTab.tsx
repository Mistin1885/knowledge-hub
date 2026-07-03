import type { Workspace } from '../../api/types';
import { useAudit } from '../../hooks/queries';
import { formatDateTime } from '../../lib/utils';
import { Button, EmptyState, ErrorNote, Spinner } from '../ui/primitives';

export default function AuditTab({ workspace }: { workspace: Workspace }) {
  const auditQ = useAudit(workspace.id);

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

  const items = auditQ.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div>
      {items.length === 0 && <EmptyState message="No audit entries yet." />}
      <div className="divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-white">
        {items.map((item) => (
          <div key={item.id} className="flex items-start gap-3 px-3 py-2.5">
            <span className="mt-0.5 flex-none rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[11px] text-neutral-600">
              {item.action}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] text-neutral-800">
                <span className="font-medium">{item.actor.name}</span>
                {item.target_title ? (
                  <>
                    {' → '}
                    <span className="font-medium">{item.target_title}</span>
                  </>
                ) : null}
                <span className="ml-1 text-xs text-neutral-400">({item.target_type})</span>
              </p>
              {item.detail && <p className="mt-0.5 text-xs text-neutral-500">{item.detail}</p>}
            </div>
            <span className="flex-none text-[11px] text-neutral-400">
              {formatDateTime(item.created_at)}
            </span>
          </div>
        ))}
      </div>
      {auditQ.hasNextPage && (
        <div className="mt-3 flex justify-center">
          <Button busy={auditQ.isFetchingNextPage} onClick={() => auditQ.fetchNextPage()}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}
