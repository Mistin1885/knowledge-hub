import { useEffect, useRef, useState } from 'react';
import type { Editor } from '@tiptap/react';
import { NodeSelection } from '@tiptap/pm/state';
import { CopyPlus, GripVertical, Trash2 } from 'lucide-react';
import { MenuItem } from '../ui/Dropdown';

interface HandleState {
  pos: number; // document position of the draggable node
  top: number; // relative to the km-editor wrapper
  left: number;
}

const LIST_ITEMS = new Set(['listItem', 'taskItem']);

/** Resolve the draggable node under `target`: an individual list item when
 *  hovering one (Notion drags bullets, not the whole list), otherwise the
 *  top-level block. Returns its doc position or null. */
function findBlock(editor: Editor, target: HTMLElement): { pos: number; dom: HTMLElement } | null {
  const dom = target.closest('li, .ProseMirror > *') as HTMLElement | null;
  if (!dom) return null;
  const view = editor.view;
  try {
    const inside = view.posAtDOM(dom, 0);
    const $pos = view.state.doc.resolve(inside);
    if (dom.tagName === 'LI') {
      for (let d = $pos.depth; d > 0; d--) {
        if (LIST_ITEMS.has($pos.node(d).type.name)) {
          return { pos: $pos.before(d), dom };
        }
      }
      return null;
    }
    const pos = $pos.depth > 0 ? $pos.before(1) : inside;
    return view.state.doc.nodeAt(pos) ? { pos, dom } : null;
  } catch {
    return null;
  }
}

/** Notion-style per-block drag handle: hover a block (or list item) to reveal
 *  it, drag to reorder — ProseMirror relocates the node — click for
 *  delete/duplicate. */
export default function BlockDragHandle({ editor }: { editor: Editor }) {
  const [handle, setHandle] = useState<HandleState | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<HandleState | null>(null);
  handleRef.current = handle;
  const draggingRef = useRef(false);
  const raf = useRef(0);

  useEffect(() => {
    const hide = () => {
      setHandle((prev) => (prev ? null : prev));
      setMenuOpen(false);
    };

    const onMove = (e: MouseEvent) => {
      if (draggingRef.current) return;
      const target = e.target as HTMLElement;
      if (rootRef.current?.contains(target)) return; // hovering the handle/menu
      const wrapper = editor.view.dom.closest('.km-editor');
      if (!wrapper || !wrapper.contains(target)) {
        // The handle floats in the gutter left of the wrapper — keep it while
        // the cursor travels there, so reaching it isn't a race.
        const cur = handleRef.current;
        if (cur && wrapper) {
          const r = wrapper.getBoundingClientRect();
          const y = e.clientY - r.top;
          const inGutter =
            e.clientX >= r.left - 56 &&
            e.clientX <= r.left + 4 &&
            y >= cur.top - 16 &&
            y <= cur.top + 40;
          if (inGutter) return;
        }
        hide();
        return;
      }
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const found = findBlock(editor, target);
        if (!found) return;
        const wrapRect = wrapper.getBoundingClientRect();
        const rect = found.dom.getBoundingClientRect();
        setHandle((prev) => {
          if (prev?.pos !== found.pos) setMenuOpen(false);
          return {
            pos: found.pos,
            top: rect.top - wrapRect.top + 2,
            left: rect.left - wrapRect.left - 26,
          };
        });
      });
    };

    // Any edit invalidates the stored block position.
    const onUpdate = () => {
      draggingRef.current = false;
      hide();
    };

    // The drop unmounts the handle button before its own dragend can fire
    // (removed drag sources never get dragend), so reset the flag here or
    // every later mousemove would be ignored and the grip never reappears.
    const onDragFinish = () => {
      draggingRef.current = false;
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('drop', onDragFinish, true);
    document.addEventListener('dragend', onDragFinish, true);
    editor.on('update', onUpdate);
    return () => {
      cancelAnimationFrame(raf.current);
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('drop', onDragFinish, true);
      document.removeEventListener('dragend', onDragFinish, true);
      editor.off('update', onUpdate);
    };
  }, [editor]);

  if (!handle) return null;

  const selectBlock = (): NodeSelection | null => {
    const view = editor.view;
    if (handle.pos >= view.state.doc.content.size || !view.state.doc.nodeAt(handle.pos)) {
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
    draggingRef.current = true;
    const view = editor.view;
    // Hand ProseMirror the dragged slice as an internal move so the drop
    // relocates the node instead of copying it.
    (view as unknown as { dragging: unknown }).dragging = { slice: sel.content(), move: true };
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', ' ');
    const dom = view.nodeDOM(handle.pos) as HTMLElement | null;
    if (dom) e.dataTransfer.setDragImage(dom, 0, 0);
    setMenuOpen(false);
  };

  const onDragEnd = () => {
    draggingRef.current = false;
    setHandle(null);
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
    // Oversized transparent hit area bridges the gap between the text edge
    // and the handle so the cursor never crosses a "dead zone" that hides it.
    <div
      ref={rootRef}
      className="absolute z-30 pb-2 pl-2 pr-1.5 pt-1.5"
      style={{ top: handle.top - 6, left: handle.left - 8 }}
    >
      <button
        draggable
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
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
