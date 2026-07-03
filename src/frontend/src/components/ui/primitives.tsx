import { forwardRef } from 'react';
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

type ButtonVariant = 'primary' | 'outline' | 'ghost' | 'danger';

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300 border border-transparent',
  outline:
    'border border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50 disabled:text-neutral-400',
  ghost: 'border border-transparent text-neutral-600 hover:bg-neutral-100 disabled:text-neutral-400',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300 border border-transparent',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  busy?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'outline', size = 'md', busy = false, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || busy}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-150',
        size === 'sm' ? 'h-7 px-2 text-xs' : 'h-8 px-3 text-[13px]',
        BUTTON_STYLES[variant],
        className,
      )}
      {...rest}
    >
      {busy && <Loader2 size={14} className="animate-spin" />}
      {children}
    </button>
  );
});

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          'h-8 w-full rounded-md border border-neutral-200 bg-white px-2.5 text-[13px] text-neutral-900',
          'placeholder:text-neutral-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100',
          'transition-colors duration-150',
          className,
        )}
        {...rest}
      />
    );
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          'w-full rounded-md border border-neutral-200 bg-white px-2.5 py-1.5 text-[13px] text-neutral-900',
          'placeholder:text-neutral-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100',
          'transition-colors duration-150',
          className,
        )}
        {...rest}
      />
    );
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          'h-8 rounded-md border border-neutral-200 bg-white px-2 text-[13px] text-neutral-900',
          'focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    );
  },
);

export function Spinner({ className }: { className?: string }) {
  return <Loader2 size={18} className={cn('animate-spin text-neutral-400', className)} />;
}

export function Centered({ children }: { children: ReactNode }) {
  return <div className="flex h-full items-center justify-center py-16">{children}</div>;
}

export function EmptyState({ message }: { message: string }) {
  return <p className="py-6 text-center text-[13px] text-neutral-400">{message}</p>;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
      {message}
    </p>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return (
    <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
      {children}
    </span>
  );
}
