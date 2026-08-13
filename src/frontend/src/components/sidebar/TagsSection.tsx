import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, Hash } from 'lucide-react';
import type { Workspace } from '../../api/types';
import { useTags } from '../../hooks/queries';

const TAGS_PER_PAGE = 50;

export default function TagsSection({ workspace }: { workspace: Workspace }) {
  const tagsQ = useTags(workspace.id);
  const tags = tagsQ.data ?? [];
  const [expanded, setExpanded] = useState(true);
  const [visibleCount, setVisibleCount] = useState(TAGS_PER_PAGE);

  useEffect(() => {
    setExpanded(true);
    setVisibleCount(TAGS_PER_PAGE);
  }, [workspace.id]);

  const toggleExpanded = () => {
    if (expanded) setVisibleCount(TAGS_PER_PAGE);
    setExpanded((current) => !current);
  };

  const visibleTags = tags.slice(0, visibleCount);

  return (
    <div className="mt-4">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={toggleExpanded}
        className="mb-1 flex w-full items-center gap-1 rounded px-1 py-0.5 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600"
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>Tags</span>
      </button>
      {expanded && (
        <>
          {tagsQ.isLoading && <p className="px-2 py-1 text-xs text-neutral-400">Loading…</p>}
          {!tagsQ.isLoading && tags.length === 0 && (
            <p className="px-2 py-1 text-xs text-neutral-400">No tags yet — add #tags to pages.</p>
          )}
          {visibleTags.map((tag) => (
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
          {visibleCount < tags.length && (
            <button
              type="button"
              onClick={() => setVisibleCount((count) => count + TAGS_PER_PAGE)}
              className="mt-1 w-full rounded-md px-2 py-1 text-left text-[12px] font-medium text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-700"
            >
              Load more
            </button>
          )}
        </>
      )}
    </div>
  );
}
