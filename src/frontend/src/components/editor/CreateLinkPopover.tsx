import { useRef } from 'react';
import { useClickOutside } from '../../hooks/useClickOutside';
import { Button } from '../ui/primitives';

export default function CreateLinkPopover({
  title,
  x,
  y,
  busy,
  onCreate,
  onCancel,
}: {
  title: string;
  x: number;
  y: number;
  busy: boolean;
  onCreate: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, onCancel);

  return (
    <div
      ref={ref}
      className="fixed z-50 w-64 rounded-md border border-neutral-200 bg-surface p-3 shadow-lg"
      style={{ left: Math.min(x, window.innerWidth - 280), top: y + 8 }}
    >
      <p className="text-[13px] text-neutral-700">
        No page titled <span className="font-medium text-neutral-900">“{title}”</span> yet.
      </p>
      <div className="mt-2.5 flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" busy={busy} onClick={onCreate}>
          Create page
        </Button>
      </div>
    </div>
  );
}
