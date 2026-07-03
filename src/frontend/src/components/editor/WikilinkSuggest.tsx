import { useEffect, useMemo, useState } from 'react';
import { FileText } from 'lucide-react';
import type { Page } from '../../api/types';
import { cn } from '../../lib/utils';
import type { WikilinkAutocompleteState } from './wikilinks';

export default function WikilinkSuggest({
  state,
  pages,
  keyHandler,
  onPick,
  onDismiss,
}: {
  state: WikilinkAutocompleteState;
  pages: Page[];
  keyHandler: { current: ((event: KeyboardEvent) => boolean) | null };
  onPick: (title: string) => void;
  onDismiss: () => void;
}) {
  const [index, setIndex] = useState(0);

  const filtered = useMemo(() => {
    const q = state.query.trim().toLowerCase();
    const matches = q
      ? pages.filter((p) => p.title.toLowerCase().includes(q))
      : pages.slice();
    matches.sort((a, b) => a.title.localeCompare(b.title));
    return matches.slice(0, 8);
  }, [pages, state.query]);

  useEffect(() => setIndex(0), [state.query]);

  useEffect(() => {
    keyHandler.current = (event: KeyboardEvent) => {
      if (event.key === 'ArrowDown') {
        setIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
        return true;
      }
      if (event.key === 'ArrowUp') {
        setIndex((i) => Math.max(i - 1, 0));
        return true;
      }
      if (event.key === 'Enter') {
        const page = filtered[index];
        if (page) {
          onPick(page.title);
          return true;
        }
        return false;
      }
      if (event.key === 'Escape') {
        onDismiss();
        return true;
      }
      return false;
    };
    return () => {
      keyHandler.current = null;
    };
  }, [filtered, index, keyHandler, onPick, onDismiss]);

  return (
    <div
      className="fixed z-50 w-64 overflow-hidden rounded-md border border-neutral-200 bg-white py-1 shadow-lg"
      style={{ left: state.left, top: state.bottom + 4 }}
    >
      {filtered.length === 0 && (
        <p className="px-3 py-2 text-xs text-neutral-400">
          No matching pages — finish with ]] to create a link.
        </p>
      )}
      {filtered.map((page, i) => (
        <button
          key={page.id}
          onMouseDown={(e) => {
            e.preventDefault();
            onPick(page.title);
          }}
          onMouseEnter={() => setIndex(i)}
          className={cn(
            'flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px]',
            i === index ? 'bg-indigo-50 text-indigo-700' : 'text-neutral-700',
          )}
        >
          {page.icon ? (
            <span className="w-4 flex-none text-center leading-none">{page.icon}</span>
          ) : (
            <FileText size={13} className="flex-none text-neutral-400" />
          )}
          <span className="truncate">{page.title}</span>
        </button>
      ))}
    </div>
  );
}
