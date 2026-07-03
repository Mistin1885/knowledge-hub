import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import type { SearchMode } from '../api/types';
import { useWorkspaceCtx } from '../components/layout/WorkspaceLayout';
import { useSearch, useTags } from '../hooks/queries';
import { cn, escapeRegExp } from '../lib/utils';
import { Button, EmptyState, ErrorNote, Input, Select, Spinner } from '../components/ui/primitives';

const MODES: SearchMode[] = ['hybrid', 'fulltext', 'semantic'];
const STATUSES = ['', 'draft', 'published', 'archived'];

function Highlighted({ text, query }: { text: string; query: string }) {
  const terms = query.split(/\s+/).filter(Boolean).map(escapeRegExp);
  if (terms.length === 0) return <>{text}</>;
  const re = new RegExp(`(${terms.join('|')})`, 'gi');
  const parts = text.split(re);
  return (
    <>
      {parts.map((part, i) =>
        // split() with one capture group alternates text / match.
        i % 2 === 1 ? (
          <mark key={i} className="rounded bg-indigo-100 px-0.5 text-indigo-900">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export default function SearchPage() {
  const { workspace } = useWorkspaceCtx();
  const [params, setParams] = useSearchParams();

  const q = params.get('q') ?? '';
  const tags = (params.get('tags') ?? '').split(',').filter(Boolean);
  const status = params.get('status') ?? '';
  const mode = (params.get('mode') as SearchMode | null) ?? 'hybrid';

  const [draft, setDraft] = useState(q);
  const tagsQ = useTags(workspace.id);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const toggleTag = (tag: string) => {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    setParam('tags', next.join(','));
  };

  const enabled = q.trim().length > 0 || tags.length > 0 || status.length > 0;
  const searchQ = useSearch(workspace.id, { q, tags, status, mode, limit: 20 }, enabled);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-8">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setParam('q', draft.trim());
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Search pages…"
              className="pl-8"
              autoFocus
            />
          </div>
          <Select value={mode} onChange={(e) => setParam('mode', e.target.value)}>
            {MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
          <Select value={status} onChange={(e) => setParam('status', e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s || 'any status'}
              </option>
            ))}
          </Select>
          <Button type="submit" variant="primary">
            Search
          </Button>
        </form>

        {(tagsQ.data ?? []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(tagsQ.data ?? []).map((tag) => (
              <button
                key={tag.name}
                onClick={() => toggleTag(tag.name)}
                className={cn(
                  'rounded-full border px-2 py-0.5 text-xs transition-colors duration-150',
                  tags.includes(tag.name)
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                    : 'border-neutral-200 bg-white text-neutral-500 hover:border-neutral-300',
                )}
              >
                #{tag.name}
              </button>
            ))}
          </div>
        )}

        <div className="mt-6">
          {!enabled && <EmptyState message="Type a query or pick a tag to search this workspace." />}
          {enabled && searchQ.isLoading && (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          )}
          {enabled && searchQ.isError && <ErrorNote message="Search failed. Try again." />}
          {enabled && searchQ.data && (
            <>
              <p className="mb-3 text-xs text-neutral-400">
                {searchQ.data.results.length} result
                {searchQ.data.results.length === 1 ? '' : 's'} · mode:{' '}
                <span className="font-medium text-neutral-500">{searchQ.data.mode_used}</span>
              </p>
              {searchQ.data.results.length === 0 && (
                <EmptyState message="No pages match this search." />
              )}
              <div className="space-y-3">
                {searchQ.data.results.map((result) => (
                  <Link
                    key={result.page.id}
                    to={`/w/${workspace.slug}/p/${result.page.id}`}
                    className="block rounded-md border border-neutral-200 bg-white px-4 py-3 transition-colors duration-150 hover:border-indigo-200"
                  >
                    <div className="flex items-center gap-2">
                      <p className="min-w-0 flex-1 truncate text-sm font-medium text-neutral-900">
                        {result.page.icon ? `${result.page.icon} ` : ''}
                        <Highlighted text={result.page.title || 'Untitled'} query={q} />
                      </p>
                      <span className="flex-none text-[11px] tabular-nums text-neutral-400">
                        {result.score.toFixed(2)}
                      </span>
                    </div>
                    {result.snippets.map((snippet, i) => (
                      <p key={i} className="mt-1.5 line-clamp-2 text-[13px] text-neutral-600">
                        {snippet.heading && (
                          <span className="mr-1.5 rounded bg-neutral-100 px-1 py-px text-[11px] text-neutral-500">
                            {snippet.heading}
                          </span>
                        )}
                        <Highlighted text={snippet.text} query={q} />
                      </p>
                    ))}
                  </Link>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
