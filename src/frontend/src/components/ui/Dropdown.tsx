import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';
import { useClickOutside } from '../../hooks/useClickOutside';

export function Dropdown({
  button,
  children,
  align = 'left',
  width = 'w-56',
}: {
  button: ReactNode;
  children: (close: () => void) => ReactNode;
  align?: 'left' | 'right';
  width?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);
  const close = () => setOpen(false);

  return (
    <div className="relative" ref={ref}>
      <div
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
      >
        {button}
      </div>
      {open && (
        <div
          className={cn(
            'absolute z-40 mt-1 rounded-md border border-neutral-200 bg-surface py-1 shadow-lg',
            align === 'right' ? 'right-0' : 'left-0',
            width,
          )}
        >
          {children(close)}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  icon,
  label,
  danger = false,
  disabled = false,
  onClick,
}: {
  icon?: ReactNode;
  label: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] transition-colors duration-150',
        danger ? 'text-red-600 hover:bg-red-50' : 'text-neutral-700 hover:bg-neutral-100',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      {icon}
      {label}
    </button>
  );
}
