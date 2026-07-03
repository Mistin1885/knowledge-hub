import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import type { PageDetail, PageStatus } from '../api/types';
import { ApiError } from '../api/client';
import { useWorkspaceCtx } from '../components/layout/WorkspaceLayout';
import { usePage, usePages } from '../hooks/queries';
import { useUpdatePage } from '../hooks/mutations';
import { useDebouncedCallback } from '../hooks/useDebouncedCallback';
import { cn } from '../lib/utils';
import CollabEditor from '../components/editor/CollabEditor';
import FolderView from '../components/folder/FolderView';
import CommentsSection from '../components/comments/CommentsSection';
import RightSidebar from '../components/rightbar/RightSidebar';
import { Dropdown } from '../components/ui/Dropdown';
import { Centered, EmptyState, ErrorNote, Spinner } from '../components/ui/primitives';

const STATUS_STYLES: Record<PageStatus, string> = {
  draft: 'bg-neutral-100 text-neutral-600',
  published: 'bg-emerald-50 text-emerald-700',
  archived: 'bg-amber-50 text-amber-700',
};

function StatusPill({ page, canEdit }: { page: PageDetail; canEdit: boolean }) {
  const update = useUpdatePage(page.id, page.workspace_id);
  const pill = (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize',
        STATUS_STYLES[page.status],
        canEdit && 'cursor-pointer',
      )}
    >
      {page.status}
      {canEdit && <ChevronDown size={12} />}
    </span>
  );

  if (!canEdit) return pill;

  return (
    <Dropdown width="w-36" align="right" button={pill}>
      {(close) => (
        <>
          {(['draft', 'published', 'archived'] as const).map((status) => (
            <button
              key={status}
              className={cn(
                'block w-full px-3 py-1.5 text-left text-[13px] capitalize transition-colors duration-150 hover:bg-neutral-100',
                status === page.status ? 'font-medium text-indigo-600' : 'text-neutral-700',
              )}
              onClick={() => {
                close();
                if (status !== page.status) update.mutate({ status });
              }}
            >
              {status}
            </button>
          ))}
        </>
      )}
    </Dropdown>
  );
}

/** Keyed by page id — local state initializes from the loaded page once. */
function PageHeader({ page, canEdit }: { page: PageDetail; canEdit: boolean }) {
  const [title, setTitle] = useState(page.title);
  const [icon, setIcon] = useState(page.icon ?? '');
  const update = useUpdatePage(page.id, page.workspace_id);

  const saveTitle = useDebouncedCallback((value: string) => {
    const trimmed = value.trim();
    if (trimmed && trimmed !== page.title) update.mutate({ title: trimmed });
  }, 600);

  const saveIcon = useDebouncedCallback((value: string) => {
    const trimmed = value.trim();
    if (trimmed !== (page.icon ?? '')) update.mutate({ icon: trimmed || null });
  }, 600);

  return (
    <div className="mb-2">
      <div className="flex items-start gap-2">
        <input
          value={icon}
          onChange={(e) => {
            setIcon(e.target.value);
            saveIcon(e.target.value);
          }}
          disabled={!canEdit}
          placeholder="📄"
          maxLength={4}
          aria-label="Page icon"
          className="mt-1 w-11 rounded-md bg-transparent text-center text-2xl outline-none transition-colors duration-150 placeholder:text-neutral-300 hover:bg-neutral-100 focus:bg-neutral-100 disabled:hover:bg-transparent"
        />
        <input
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            saveTitle(e.target.value);
          }}
          disabled={!canEdit}
          placeholder="Untitled"
          aria-label="Page title"
          className="min-w-0 flex-1 bg-transparent text-3xl font-semibold tracking-tight text-neutral-900 outline-none placeholder:text-neutral-300"
        />
        <div className="mt-2 flex-none">
          <StatusPill page={page} canEdit={canEdit} />
        </div>
      </div>
    </div>
  );
}

export default function EditorPage() {
  const { pageId = '' } = useParams();
  const { workspace, user } = useWorkspaceCtx();
  const pageQ = usePage(pageId);
  const pagesQ = usePages(workspace.id);
  const canEdit = workspace.my_role !== 'viewer';

  if (pageQ.isLoading) {
    return (
      <Centered>
        <Spinner />
      </Centered>
    );
  }

  if (pageQ.isError || !pageQ.data) {
    const notFound = pageQ.error instanceof ApiError && pageQ.error.status === 404;
    return (
      <Centered>
        {notFound ? (
          <EmptyState message="This page does not exist (or was deleted)." />
        ) : (
          <ErrorNote message="Failed to load this page." />
        )}
      </Centered>
    );
  }

  const page = pageQ.data;

  return (
    <div className="flex h-full min-h-0">
      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-8 py-8">
          {/* sibling keys must be unique — sharing page.id corrupts reconciliation */}
          <PageHeader key={`header:${page.id}`} page={page} canEdit={canEdit} />
          {page.is_folder ? (
            <FolderView
              key={`folder:${page.id}`}
              page={page}
              workspace={workspace}
              canEdit={canEdit}
            />
          ) : (
            <CollabEditor
              key={`editor:${page.id}`}
              pageId={page.id}
              workspace={workspace}
              user={user}
              pages={pagesQ.data ?? []}
              editable={canEdit}
            />
          )}
          <CommentsSection pageId={page.id} user={user} canComment={canEdit} />
        </div>
      </div>
      <RightSidebar page={page} workspace={workspace} canEdit={canEdit} />
    </div>
  );
}
