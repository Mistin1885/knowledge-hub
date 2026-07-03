import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { FileText, Hash } from 'lucide-react';
import { useWorkspaceCtx } from '../components/layout/WorkspaceLayout';
import { usePages } from '../hooks/queries';
import { timeAgo } from '../lib/utils';
import { Centered, EmptyState, ErrorNote, Spinner } from '../components/ui/primitives';

export default function TagPage() {
  const { tag = '' } = useParams();
  const { workspace } = useWorkspaceCtx();
  const pagesQ = usePages(workspace.id);

  const tagged = useMemo(
    () =>
      (pagesQ.data ?? [])
        .filter((p) => p.tags.some((t) => t.toLowerCase() === tag.toLowerCase()))
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [pagesQ.data, tag],
  );

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

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-10">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-neutral-900">
          <Hash size={20} className="text-indigo-500" />
          {tag}
          <span className="text-sm font-normal text-neutral-400">
            {tagged.length} page{tagged.length === 1 ? '' : 's'}
          </span>
        </h1>
        {tagged.length === 0 && (
          <EmptyState message="No pages carry this tag (that you can see)." />
        )}
        <div className="mt-4 divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-surface">
          {tagged.map((page) => (
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
                {page.title || 'Untitled'}
              </span>
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
