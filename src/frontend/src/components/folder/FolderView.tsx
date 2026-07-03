import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileText, Folder, Plus, StickyNote } from 'lucide-react';
import type { ChildPage } from '../../api/endpoints';
import type { PageDetail, Workspace } from '../../api/types';
import { useChildren } from '../../hooks/queries';
import { useCreatePage, useUpdatePage } from '../../hooks/mutations';
import { useDebouncedCallback } from '../../hooks/useDebouncedCallback';
import { cn, formatDateTime } from '../../lib/utils';
import { EmptyState, ErrorNote, Spinner } from '../ui/primitives';

const STATUS_DOT: Record<string, string> = {
  draft: 'bg-neutral-300',
  published: 'bg-emerald-400',
  archived: 'bg-amber-400',
};

/** Notion-like folder page: folder-level notes + sub-page preview list,
 *  with a per-item annotation on every child. */
export default function FolderView({
  page,
  workspace,
  canEdit,
}: {
  page: PageDetail;
  workspace: Workspace;
  canEdit: boolean;
}) {
  const childrenQ = useChildren(page.id);
  const createPage = useCreatePage(workspace.id);
  const navigate = useNavigate();

  const newChild = (isFolder: boolean) => {
    createPage.mutate(
      { title: isFolder ? 'New folder' : 'Untitled', parent_id: page.id, is_folder: isFolder },
      { onSuccess: (created) => navigate(`/w/${workspace.slug}/p/${created.id}`) },
    );
  };

  return (
    <div>
      <FolderNotes key={`notes:${page.id}`} page={page} canEdit={canEdit} />

      <div className="mb-2 mt-6 flex items-center justify-between">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
          Pages in this folder
        </h2>
        {canEdit && (
          <div className="flex gap-1">
            <button
              onClick={() => newChild(false)}
              disabled={createPage.isPending}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-800"
            >
              <Plus size={13} /> Page
            </button>
            <button
              onClick={() => newChild(true)}
              disabled={createPage.isPending}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-800"
            >
              <Plus size={13} /> Folder
            </button>
          </div>
        )}
      </div>

      {childrenQ.isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {childrenQ.isError && <ErrorNote message="Failed to load this folder's pages." />}
      {childrenQ.data && childrenQ.data.length === 0 && (
        <EmptyState message="This folder is empty — add a page above." />
      )}

      <div className="space-y-2">
        {(childrenQ.data ?? []).map((child) => (
          <ChildCard
            key={child.page.id}
            child={child}
            workspace={workspace}
            canEdit={canEdit}
          />
        ))}
      </div>
    </div>
  );
}

/** Folder-level annotation area, persisted as the folder page's markdown body. */
function FolderNotes({ page, canEdit }: { page: PageDetail; canEdit: boolean }) {
  const [value, setValue] = useState(page.content_md);
  const update = useUpdatePage(page.id, page.workspace_id);
  const save = useDebouncedCallback((next: string) => {
    if (next !== page.content_md) update.mutate({ content_md: next });
  }, 800);

  if (!canEdit && !value.trim()) return null;

  return (
    <textarea
      value={value}
      onChange={(e) => {
        setValue(e.target.value);
        save(e.target.value);
      }}
      readOnly={!canEdit}
      rows={Math.min(8, Math.max(2, value.split('\n').length))}
      placeholder="Folder notes — describe what belongs here, conventions, owners…"
      className="w-full resize-none rounded-md border border-transparent bg-neutral-50 px-3 py-2 text-[13.5px] leading-relaxed text-neutral-700 outline-none transition-colors duration-150 placeholder:text-neutral-400 focus:border-neutral-200 focus:bg-white"
    />
  );
}

function ChildCard({
  child,
  workspace,
  canEdit,
}: {
  child: ChildPage;
  workspace: Workspace;
  canEdit: boolean;
}) {
  const { page } = child;
  return (
    <div className="group rounded-md border border-neutral-200 bg-white px-3 py-2.5 transition-colors duration-150 hover:border-neutral-300">
      <div className="flex items-center gap-2">
        <span className="w-5 flex-none text-center text-[15px] leading-none">
          {page.icon ||
            (page.is_folder ? (
              <Folder size={15} className="inline text-neutral-400" />
            ) : (
              <FileText size={15} className="inline text-neutral-400" />
            ))}
        </span>
        <Link
          to={`/w/${workspace.slug}/p/${page.id}`}
          className="min-w-0 flex-1 truncate text-[14px] font-medium text-neutral-900 hover:text-indigo-600 hover:underline"
        >
          {page.title || 'Untitled'}
        </Link>
        <span
          className={cn('h-1.5 w-1.5 flex-none rounded-full', STATUS_DOT[page.status])}
          title={page.status}
        />
        <span className="flex-none text-[11px] text-neutral-400">
          {formatDateTime(page.updated_at)}
        </span>
      </div>
      {child.preview && (
        <p className="mt-1 line-clamp-2 pl-7 text-[12.5px] leading-relaxed text-neutral-500">
          {child.preview}
        </p>
      )}
      <ChildNote child={child} canEdit={canEdit} />
    </div>
  );
}

/** Per-item annotation, stored on the child page as metadata["note"]. */
function ChildNote({ child, canEdit }: { child: ChildPage; canEdit: boolean }) {
  const { page } = child;
  const [value, setValue] = useState(page.metadata.note ?? '');
  const update = useUpdatePage(page.id, page.workspace_id);
  const save = useDebouncedCallback((next: string) => {
    const trimmed = next.trim();
    if (trimmed === (page.metadata.note ?? '')) return;
    const metadata = { ...page.metadata };
    if (trimmed) metadata.note = trimmed;
    else delete metadata.note;
    update.mutate({ metadata });
  }, 800);

  if (!canEdit && !value.trim()) return null;

  return (
    <div className="mt-1.5 flex items-start gap-1.5 pl-7">
      <StickyNote size={12} className="mt-1 flex-none text-amber-400" />
      <input
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          save(e.target.value);
        }}
        readOnly={!canEdit}
        placeholder="Add a note about this page…"
        className={cn(
          'min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-[12.5px] text-neutral-600 outline-none transition-colors duration-150 placeholder:text-neutral-300',
          canEdit && 'hover:bg-amber-50/60 focus:bg-amber-50/60',
          !value.trim() && 'opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100',
        )}
      />
    </div>
  );
}
