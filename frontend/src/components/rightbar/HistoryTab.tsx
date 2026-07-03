import { useState } from 'react';
import type { PageDetail } from '../../api/types';
import { useVersionDetail, useVersions } from '../../hooks/queries';
import { useRestoreVersion } from '../../hooks/mutations';
import { timeAgo } from '../../lib/utils';
import { Modal } from '../ui/Modal';
import { Button, EmptyState, Spinner } from '../ui/primitives';

export default function HistoryTab({ page, canEdit }: { page: PageDetail; canEdit: boolean }) {
  const versionsQ = useVersions(page.id);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const versionQ = useVersionDetail(page.id, previewId);
  const restore = useRestoreVersion(page.id);

  if (versionsQ.isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }
  if (versionsQ.isError) return <EmptyState message="Could not load version history." />;

  const versions = versionsQ.data ?? [];
  if (versions.length === 0) {
    return <EmptyState message="No versions yet — they appear as the page is edited." />;
  }

  return (
    <div className="space-y-0.5">
      {versions.map((v) => (
        <button
          key={v.id}
          onClick={() => setPreviewId(v.id)}
          className="block w-full rounded-md px-2 py-1.5 text-left transition-colors duration-150 hover:bg-neutral-100"
        >
          <div className="flex items-center gap-2">
            <span className="rounded bg-neutral-100 px-1.5 py-px font-mono text-[11px] text-neutral-600">
              v{v.version}
            </span>
            <span className="min-w-0 flex-1 truncate text-[13px] text-neutral-800">{v.title}</span>
          </div>
          <p className="mt-0.5 text-[11px] text-neutral-400">
            {v.created_by.name} · {timeAgo(v.created_at)}
            {v.summary ? ` · ${v.summary}` : ''}
          </p>
        </button>
      ))}

      {previewId && (
        <Modal
          title={
            versionQ.data ? `Version ${versionQ.data.version} — ${versionQ.data.title}` : 'Version'
          }
          onClose={() => setPreviewId(null)}
          wide
        >
          {versionQ.isLoading && (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          )}
          {versionQ.isError && <EmptyState message="Could not load this version." />}
          {versionQ.data && (
            <>
              <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap rounded-md border border-neutral-200 bg-neutral-50 p-3 font-mono text-xs leading-5 text-neutral-800">
                {versionQ.data.content_md || '(empty)'}
              </pre>
              {canEdit && (
                <div className="mt-3 flex justify-end">
                  <Button
                    variant="primary"
                    busy={restore.isPending}
                    onClick={() =>
                      restore.mutate(previewId, { onSuccess: () => setPreviewId(null) })
                    }
                  >
                    Restore this version
                  </Button>
                </div>
              )}
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
