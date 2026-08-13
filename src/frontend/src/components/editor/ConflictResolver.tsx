import { useMemo, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { ContentConflict } from '../../api/types';
import { Button, Textarea } from '../ui/primitives';

function conflictText(base: string, server: string, mine: string): string {
  if (mine === base) return server;
  if (server === base || server === mine) return mine;
  return [
    '<<<<<<< 我的版本',
    mine,
    '||||||| 開始編輯時',
    base,
    '=======',
    server,
    '>>>>>>> 伺服器最新版本',
  ].join('\n');
}

function ComparePane({ title, value }: { title: string; value: string }) {
  return (
    <section className="min-w-0">
      <h3 className="mb-1 text-xs font-semibold text-neutral-600">{title}</h3>
      <pre className="h-52 overflow-auto whitespace-pre-wrap rounded-md border border-neutral-200 bg-neutral-50 p-2 font-mono text-[11px] leading-relaxed text-neutral-700">
        {value || '(空白)'}
      </pre>
    </section>
  );
}

export default function ConflictResolver({
  base,
  conflict,
  busy,
  onSave,
  onCancel,
}: {
  base: string;
  conflict: ContentConflict;
  busy: boolean;
  onSave: (resolved: string) => void;
  onCancel: () => void;
}) {
  const initial = useMemo(
    () => conflictText(base, conflict.current_content_md, conflict.proposed_content_md),
    [base, conflict],
  );
  const [resolved, setResolved] = useState(initial);
  const hasMarkers = /^(<<<<<<<|\|\|\|\|\|\|\||=======|>>>>>>>)/m.test(resolved);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative flex max-h-[94vh] w-full max-w-7xl flex-col overflow-hidden rounded-lg border border-neutral-200 bg-surface shadow-xl">
        <header className="flex items-center gap-2 border-b border-neutral-200 px-5 py-3">
          <AlertTriangle size={17} className="text-amber-500" />
          <div>
            <h2 className="text-sm font-semibold text-neutral-900">這個 Page 已被其他人修改</h2>
            <p className="text-xs text-neutral-500">
              比較三個版本，選擇一側或在下方移除衝突標記後儲存。
            </p>
          </div>
        </header>
        <div className="min-h-0 overflow-y-auto p-5">
          <div className="grid gap-3 lg:grid-cols-3">
            <ComparePane title="開始編輯時（Base）" value={base} />
            <ComparePane title="伺服器最新版本" value={conflict.current_content_md} />
            <ComparePane title="我的未儲存版本" value={conflict.proposed_content_md} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="mr-1 text-xs font-semibold text-neutral-600">解決結果</span>
            <Button size="sm" onClick={() => setResolved(conflict.current_content_md)}>
              使用伺服器版本
            </Button>
            <Button size="sm" onClick={() => setResolved(conflict.proposed_content_md)}>
              使用我的版本
            </Button>
            <Button size="sm" onClick={() => setResolved(initial)}>
              重設衝突標記
            </Button>
          </div>
          <Textarea
            value={resolved}
            onChange={(event) => setResolved(event.target.value)}
            rows={18}
            spellCheck={false}
            className="mt-2 min-h-72 resize-y font-mono text-xs leading-relaxed"
          />
          {hasMarkers && (
            <p className="mt-2 text-xs text-amber-700">
              仍有 Git 樣式的衝突標記；請決定要保留的內容並移除標記。
            </p>
          )}
        </div>
        <footer className="flex justify-end gap-2 border-t border-neutral-200 px-5 py-3">
          <Button variant="ghost" onClick={onCancel}>稍後處理</Button>
          <Button
            variant="primary"
            busy={busy}
            disabled={hasMarkers}
            onClick={() => onSave(resolved)}
          >
            儲存解決結果
          </Button>
        </footer>
      </div>
    </div>
  );
}
