import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Editor } from '@tiptap/react';
import {
  Bold,
  Code,
  Heading1,
  Heading2,
  Heading3,
  Italic,
  Link2,
  List,
  ListOrdered,
  Pilcrow,
  SquareCode,
  Strikethrough,
  TextQuote,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button, Input } from '../ui/primitives';

interface Pos {
  x: number;
  y: number;
}

const MENU_WIDTH = 224;
const MENU_MAX_HEIGHT = 380;

function clamp(pos: Pos): Pos {
  return {
    x: Math.min(pos.x, window.innerWidth - MENU_WIDTH - 8),
    y: Math.min(pos.y, window.innerHeight - MENU_MAX_HEIGHT - 8),
  };
}

function MenuButton({
  icon,
  label,
  shortcut,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  shortcut?: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onMouseDown={(e) => e.preventDefault()} // keep the editor selection
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] transition-colors duration-150 hover:bg-neutral-100',
        active ? 'font-medium text-indigo-600' : 'text-neutral-700',
      )}
    >
      <span className="flex-none text-neutral-400">{icon}</span>
      <span className="flex-1">{label}</span>
      {shortcut && <span className="text-[11px] text-neutral-400">{shortcut}</span>}
    </button>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="px-3 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
      {children}
    </p>
  );
}

/** Notion-style right-click formatting menu for the current text selection. */
export default function SelectionMenu({ editor, pos, onClose }: {
  editor: Editor;
  pos: Pos;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [linkMode, setLinkMode] = useState(false);
  const [href, setHref] = useState('');

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  const run = (fn: () => void) => {
    fn();
    onClose();
  };
  const chain = () => editor.chain().focus();

  const applyLink = () => {
    const url = href.trim();
    if (url) {
      chain().extendMarkRange('link').setLink({ href: url }).run();
    } else {
      chain().extendMarkRange('link').unsetLink().run();
    }
    onClose();
  };

  const { x, y } = clamp(pos);

  return createPortal(
    <div
      ref={ref}
      style={{ left: x, top: y, width: MENU_WIDTH }}
      className="fixed z-50 max-h-[380px] overflow-y-auto rounded-md border border-neutral-200 bg-surface py-1 shadow-lg"
    >
      {linkMode ? (
        <form
          className="px-3 py-2"
          onSubmit={(e) => {
            e.preventDefault();
            applyLink();
          }}
        >
          <p className="mb-1 text-[11px] font-medium text-neutral-500">Link URL</p>
          <Input
            autoFocus
            value={href}
            onChange={(e) => setHref(e.target.value)}
            placeholder="https://…"
          />
          <div className="mt-2 flex justify-end gap-1.5">
            <Button type="button" size="sm" variant="ghost" onClick={() => setLinkMode(false)}>
              Back
            </Button>
            <Button type="submit" size="sm" variant="primary">
              {href.trim() ? 'Apply' : 'Remove link'}
            </Button>
          </div>
        </form>
      ) : (
        <>
          <SectionLabel>Turn into</SectionLabel>
          <MenuButton
            icon={<Pilcrow size={13} />}
            label="Text"
            active={editor.isActive('paragraph')}
            onClick={() => run(() => chain().setParagraph().run())}
          />
          <MenuButton
            icon={<Heading1 size={13} />}
            label="Heading 1"
            active={editor.isActive('heading', { level: 1 })}
            onClick={() => run(() => chain().toggleHeading({ level: 1 }).run())}
          />
          <MenuButton
            icon={<Heading2 size={13} />}
            label="Heading 2"
            active={editor.isActive('heading', { level: 2 })}
            onClick={() => run(() => chain().toggleHeading({ level: 2 }).run())}
          />
          <MenuButton
            icon={<Heading3 size={13} />}
            label="Heading 3"
            active={editor.isActive('heading', { level: 3 })}
            onClick={() => run(() => chain().toggleHeading({ level: 3 }).run())}
          />
          <MenuButton
            icon={<List size={13} />}
            label="Bulleted list"
            active={editor.isActive('bulletList')}
            onClick={() => run(() => chain().toggleBulletList().run())}
          />
          <MenuButton
            icon={<ListOrdered size={13} />}
            label="Numbered list"
            active={editor.isActive('orderedList')}
            onClick={() => run(() => chain().toggleOrderedList().run())}
          />
          <MenuButton
            icon={<TextQuote size={13} />}
            label="Quote"
            active={editor.isActive('blockquote')}
            onClick={() => run(() => chain().toggleBlockquote().run())}
          />
          <MenuButton
            icon={<SquareCode size={13} />}
            label="Code block"
            active={editor.isActive('codeBlock')}
            onClick={() => run(() => chain().toggleCodeBlock().run())}
          />
          <div className="my-1 border-t border-neutral-100" />
          <SectionLabel>Format</SectionLabel>
          <MenuButton
            icon={<Bold size={13} />}
            label="Bold"
            shortcut="⌘B"
            active={editor.isActive('bold')}
            onClick={() => run(() => chain().toggleBold().run())}
          />
          <MenuButton
            icon={<Italic size={13} />}
            label="Italic"
            shortcut="⌘I"
            active={editor.isActive('italic')}
            onClick={() => run(() => chain().toggleItalic().run())}
          />
          <MenuButton
            icon={<Strikethrough size={13} />}
            label="Strikethrough"
            active={editor.isActive('strike')}
            onClick={() => run(() => chain().toggleStrike().run())}
          />
          <MenuButton
            icon={<Code size={13} />}
            label="Inline code"
            shortcut="⌘E"
            active={editor.isActive('code')}
            onClick={() => run(() => chain().toggleCode().run())}
          />
          <MenuButton
            icon={<Link2 size={13} />}
            label={editor.isActive('link') ? 'Edit link…' : 'Add link…'}
            active={editor.isActive('link')}
            onClick={() => {
              setHref((editor.getAttributes('link').href as string | undefined) ?? '');
              setLinkMode(true);
            }}
          />
        </>
      )}
    </div>,
    document.body,
  );
}
