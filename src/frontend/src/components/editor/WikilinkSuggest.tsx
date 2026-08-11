import { useEffect, useMemo, useState } from 'react';
import { File, FileImage, FileText, Folder } from 'lucide-react';
import type { Page } from '../../api/types';
import { cn } from '../../lib/utils';
import { vaultPath } from '../../lib/tree';
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
  onPick: (page: Page) => void;
  onDismiss: () => void;
}) {
  const [index, setIndex] = useState(0);

  const filtered = useMemo(() => {
    const q = state.query.trim().toLowerCase();
    const matches = q
      ? pages.filter((p) => vaultPath(pages, p.id).toLowerCase().includes(q))
      : pages.slice();
    matches.sort((a, b) => vaultPath(pages, a.id).localeCompare(vaultPath(pages, b.id)));
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
          onPick(page);
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
      className="fixed z-50 w-64 overflow-hidden rounded-md border border-neutral-200 bg-surface py-1 shadow-lg"
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
            onPick(page);
          }}
          onMouseEnter={() => setIndex(i)}
          className={cn(
            'flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px]',
            i === index ? 'bg-indigo-50 text-indigo-700' : 'text-neutral-700',
          )}
        >
          {page.icon ? (
            <span className="w-4 flex-none text-center leading-none">{page.icon}</span>
          ) : page.node_type === 'folder' ? (
            <Folder size={13} className="flex-none text-neutral-400" />
          ) : page.preview_kind === 'image' ? (
            <FileImage size={13} className="flex-none text-neutral-400" />
          ) : page.node_type === 'file' ? (
            <File size={13} className="flex-none text-neutral-400" />
          ) : (
            <FileText size={13} className="flex-none text-neutral-400" />
          )}
          <span className="min-w-0 flex-1 truncate">{page.title}</span>
          <span className="max-w-28 truncate text-[10px] text-neutral-400">
            {vaultPath(pages, page.id).split('/').slice(0, -1).join('/')}
          </span>
        </button>
      ))}
    </div>
  );
}
