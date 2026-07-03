import { useEffect, useRef, useState } from 'react';
import type { Editor } from '@tiptap/react';
import { NodeSelection } from '@tiptap/pm/state';
import { CopyPlus, GripVertical, Trash2 } from 'lucide-react';
import { MenuItem } from '../ui/Dropdown';

interface HandleState {
  pos: number; // document position of the top-level block
  top: number; // relative to the km-editor wrapper
  left: number;
}

/** Notion-style per-block drag handle: hover a block to reveal it, drag to
 *  reorder (ProseMirror moves the node), click for delete/duplicate. */
export default function BlockDragHandle({ editor }: { editor: Editor }) {
  const [handle, setHandle] = useState<HandleState | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const raf = useRef(0);

  useEffect(() => {
    const wrapper = rootRef.current?.parentElement; // the .km-editor wrapper
    if (!wrapper) return;

    const locate = (target: HTMLElement): HandleState | null => {
      const blockEl = target.closest('.ProseMirror > *') as HTMLElement | null;
      if (!blockEl) return null;
      const view = editor.view;
      let pos: number;
      try {
        const inside = view.posAtDOM(blockEl, 0);
        const $pos = view.state.doc.resolve(inside);
        pos = $pos.depth > 0 ? $pos.before(1) : inside;
      } catch {
        return null;
      }
      if (!view.state.doc.nodeAt(pos)) return null;
      const blockRect = blockEl.getBoundingClientRect();
      const wrapRect = wrapper.getBoundingClientRect();
      return {
        pos,
        top: blockRect.top - wrapRect.top + 2,
        left: blockRect.left - wrapRect.left - 28,
      };
    };

    const onMove = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (rootRef.current?.contains(target)) return; // hovering the handle itself
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const next = locate(target);
        if (next) {
          setHandle((prev) => {
            if (prev?.pos !== next.pos) setMenuOpen(false);
            return next;
          });
        }
      });
    };
    const onLeave = () => {
      cancelAnimationFrame(raf.current);
      setHandle(null);
      setMenuOpen(false);
    };

    wrapper.addEventListener('mousemove', onMove);
    wrapper.addEventListener('mouseleave', onLeave);
    return () => {
      cancelAnimationFrame(raf.current);
      wrapper.removeEventListener('mousemove', onMove);
      wrapper.removeEventListener('mouseleave', onLeave);
    };
  }, [editor]);

  // Any edit invalidates the stored block position.
  useEffect(() => {
    const hide = () => {
      setHandle(null);
      setMenuOpen(false);
    };
    editor.on('update', hide);
    return () => {
      editor.off('update', hide);
    };
  }, [editor]);

  if (!handle) return null;

  const selectBlock = (): NodeSelection | null => {
    const view = editor.view;
    if (handle.pos > view.state.doc.content.size || !view.state.doc.nodeAt(handle.pos)) {
      return null;
    }
    const sel = NodeSelection.create(view.state.doc, handle.pos);
    view.dispatch(view.state.tr.setSelection(sel));
    return sel;
  };

  const onDragStart = (e: React.DragEvent) => {
    const sel = selectBlock();
    if (!sel) {
      e.preventDefault();
      return;
    }
    const view = editor.view;
    // Hand ProseMirror the dragged slice as an internal move so the drop
    // relocates the node instead of copying it.
    (view as unknown as { dragging: unknown }).dragging = { slice: sel.content(), move: true };
    e.dataTransfer.effectAllowed = 'move';
    const dom = view.nodeDOM(handle.pos) as HTMLElement | null;
    e.dataTransfer.setData('text/plain', dom?.textContent ?? ' ');
    if (dom) e.dataTransfer.setDragImage(dom, 0, 0);
    setMenuOpen(false);
  };

  const deleteBlock = () => {
    const view = editor.view;
    const node = view.state.doc.nodeAt(handle.pos);
    if (node) view.dispatch(view.state.tr.delete(handle.pos, handle.pos + node.nodeSize));
    setHandle(null);
    setMenuOpen(false);
    editor.commands.focus();
  };

  const duplicateBlock = () => {
    const view = editor.view;
    const node = view.state.doc.nodeAt(handle.pos);
    if (node) view.dispatch(view.state.tr.insert(handle.pos + node.nodeSize, node));
    setHandle(null);
    setMenuOpen(false);
    editor.commands.focus();
  };

  return (
    <div
      ref={rootRef}
      className="absolute z-30"
      style={{ top: handle.top, left: handle.left }}
    >
      <button
        draggable
        onDragStart={onDragStart}
        onDragEnd={() => setHandle(null)}
        onClick={() => {
          selectBlock();
          setMenuOpen((o) => !o);
        }}
        title="Drag to move, click for options"
        className="cursor-grab rounded p-0.5 text-neutral-300 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-500 active:cursor-grabbing"
      >
        <GripVertical size={16} />
      </button>
      {menuOpen && (
        <div className="absolute left-0 top-6 w-40 rounded-md border border-neutral-200 bg-surface py-1 shadow-lg">
          <MenuItem icon={<CopyPlus size={13} />} label="Duplicate" onClick={duplicateBlock} />
          <MenuItem icon={<Trash2 size={13} />} label="Delete" danger onClick={deleteBlock} />
        </div>
      )}
    </div>
  );
}
