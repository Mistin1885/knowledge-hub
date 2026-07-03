import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Unlink } from 'lucide-react';
import { useWorkspaceCtx } from '../components/layout/WorkspaceLayout';
import { useOrphans, usePages } from '../hooks/queries';
import { timeAgo } from '../lib/utils';
import { Centered, EmptyState, ErrorNote, Spinner } from '../components/ui/primitives';

export default function WorkspaceHome() {
  const { workspace } = useWorkspaceCtx();
  const pagesQ = usePages(workspace.id);
  const orphansQ = useOrphans(workspace.id);

  const recent = useMemo(
    () =>
      [...(pagesQ.data ?? [])]
        .filter((p) => !p.is_folder)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
        .slice(0, 12),
    [pagesQ.data],
  );

  // Ancestor-folder prefix ("folder/sub folder") for each recent page.
  const pathPrefix = useMemo(() => {
    const byId = new Map((pagesQ.data ?? []).map((p) => [p.id, p]));
    return (pageId: string): string => {
      const segments: string[] = [];
      let current = byId.get(pageId);
      while (current?.parent_id && segments.length < 10) {
        const parent = byId.get(current.parent_id);
        if (!parent) break;
        segments.unshift(parent.title || 'Untitled');
        current = parent;
      }
      return segments.join('/');
    };
  }, [pagesQ.data]);

  if (pagesQ.isLoading) {
    return (
      <Centered>
        <Spinner />
      </Centered>
    );
  }
  if (pagesQ.isError) {
    return (
      <Centered>
        <ErrorNote message="Failed to load pages." />
      </Centered>
    );
  }

  const orphans = orphansQ.data ?? [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-10">
        <h1 className="text-xl font-semibold tracking-tight text-neutral-900">
          {workspace.icon ? `${workspace.icon} ` : ''}
          {workspace.name}
        </h1>
        {workspace.description && (
          <p className="mt-1 text-[13px] text-neutral-500">{workspace.description}</p>
        )}

        {orphans.length > 0 && (
          <div className="mt-6 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5">
            <Unlink size={14} className="mt-0.5 flex-none text-amber-600" />
            <div className="text-[13px] text-amber-800">
              <p>
                {orphans.length} page{orphans.length === 1 ? '' : 's'} without any links —
                consider connecting them:
              </p>
              <p className="mt-1 space-x-2">
                {orphans.slice(0, 5).map((p) => (
                  <Link
                    key={p.id}
                    to={`/w/${workspace.slug}/p/${p.id}`}
                    className="font-medium underline decoration-amber-300 underline-offset-2 hover:text-amber-900"
                  >
                    {p.title || 'Untitled'}
                  </Link>
                ))}
                {orphans.length > 5 && <span>…</span>}
              </p>
            </div>
          </div>
        )}

        <h2 className="mb-2 mt-8 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
          Recently updated
        </h2>
        {recent.length === 0 && (
          <EmptyState message="Nothing here yet — create a page from the sidebar." />
        )}
        <div className="divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-surface">
          {recent.map((page) => (
            <Link
              key={page.id}
              to={`/w/${workspace.slug}/p/${page.id}`}
              className="flex items-center gap-2.5 px-3 py-2 transition-colors duration-150 hover:bg-neutral-50"
            >
              {page.icon ? (
                <span className="w-4 flex-none text-center text-sm leading-none">{page.icon}</span>
              ) : (
                <FileText size={14} className="flex-none text-neutral-400" />
              )}
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-neutral-800">
                {pathPrefix(page.id) && (
                  <span className="font-normal text-neutral-400">{pathPrefix(page.id)}/</span>
                )}
                {page.title || 'Untitled'}
              </span>
              {page.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="hidden flex-none rounded-full bg-indigo-50 px-1.5 py-px text-[10px] text-indigo-600 sm:inline"
                >
                  #{tag}
                </span>
              ))}
              <span className="flex-none text-[11px] text-neutral-400">
                {timeAgo(page.updated_at)}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
