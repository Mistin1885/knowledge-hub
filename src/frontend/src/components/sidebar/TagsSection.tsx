import { Link } from 'react-router-dom';
import { Hash } from 'lucide-react';
import type { Workspace } from '../../api/types';
import { useTags } from '../../hooks/queries';

export default function TagsSection({ workspace }: { workspace: Workspace }) {
  const tagsQ = useTags(workspace.id);
  const tags = tagsQ.data ?? [];

  return (
    <div className="mt-4">
      <p className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
        Tags
      </p>
      {tagsQ.isLoading && <p className="px-2 py-1 text-xs text-neutral-400">Loading…</p>}
      {!tagsQ.isLoading && tags.length === 0 && (
        <p className="px-2 py-1 text-xs text-neutral-400">No tags yet — add #tags to pages.</p>
      )}
      {tags.map((tag) => (
        <Link
          key={tag.name}
          to={`/w/${workspace.slug}/tags/${encodeURIComponent(tag.name)}`}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] text-neutral-600 transition-colors duration-150 hover:bg-neutral-100"
        >
          <Hash size={13} className="flex-none text-neutral-400" />
          <span className="min-w-0 flex-1 truncate">{tag.name}</span>
          <span className="text-[11px] text-neutral-400">{tag.page_count}</span>
        </Link>
      ))}
    </div>
  );
}
