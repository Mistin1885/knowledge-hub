import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Table from '@tiptap/extension-table';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import TableRow from '@tiptap/extension-table-row';
import Placeholder from '@tiptap/extension-placeholder';
import type { EditorView } from '@tiptap/pm/view';
import type { ContentConflict, Page, PageDetail, RuntimeConfig, Workspace } from '../../api/types';
import { ApiError } from '../../api/client';
import { pageApi } from '../../api/endpoints';
import { useCreatePage } from '../../hooks/mutations';
import { vaultPath } from '../../lib/tree';
import { Button } from '../ui/primitives';
import { Wikilinks, type WikilinkAutocompleteState } from './wikilinks';
import WikilinkSuggest from './WikilinkSuggest';
import CreateLinkPopover from './CreateLinkPopover';
import SelectionMenu from './SelectionMenu';
import BlockDragHandle from './BlockDragHandle';
import ConflictResolver from './ConflictResolver';
import { ColoredTextStyle, CopyableCodeBlock } from './editorExtensions';
import { imageFiles, insertImagesAt } from './CollabEditor';

type SaveStatus = 'saved' | 'dirty' | 'saving' | 'error';

interface Draft {
  baseRevision: string;
  baseMarkdown: string;
  editorDoc: Record<string, unknown>;
}

function draftKey(pageId: string) {
  return `km:standard-draft:${pageId}`;
}

export default function StandardEditor({
  page,
  workspace,
  pages,
  editable,
  config,
  onSaved,
}: {
  page: PageDetail;
  workspace: Workspace;
  pages: Page[];
  editable: boolean;
  config: RuntimeConfig;
  onSaved: (page: PageDetail) => void;
}) {
  const navigate = useNavigate();
  const createPage = useCreatePage(workspace.id);
  const pagesRef = useRef(pages);
  pagesRef.current = pages;
  const [initialDraft] = useState(() => {
    try {
      const raw = localStorage.getItem(draftKey(page.id));
      if (raw) {
        const draft = JSON.parse(raw) as Draft;
        // Restore even when the server revision advanced while this browser
        // was away. The first Save will then open the normal three-way
        // conflict resolver instead of silently discarding the local draft.
        if (draft.baseRevision && draft.baseMarkdown !== undefined && draft.editorDoc) {
          return { draft, restored: true };
        }
      }
    } catch {
      localStorage.removeItem(draftKey(page.id));
    }
    return {
      draft: {
        baseRevision: page.content_revision,
        baseMarkdown: page.content_md,
        editorDoc: page.editor_doc,
      },
      restored: false,
    };
  });
  const savedRevisionRef = useRef(initialDraft.draft.baseRevision);
  const baseMarkdownRef = useRef(initialDraft.draft.baseMarkdown);
  const savedDocumentRef = useRef(
    initialDraft.restored ? null : JSON.stringify(initialDraft.draft.editorDoc),
  );
  const [status, setStatus] = useState<SaveStatus>(initialDraft.restored ? 'dirty' : 'saved');
  const [conflict, setConflict] = useState<ContentConflict | null>(null);
  const [imageUploads, setImageUploads] = useState(0);
  const [imageUploadError, setImageUploadError] = useState(false);
  const [autocomplete, setAutocomplete] = useState<WikilinkAutocompleteState | null>(null);
  const [createLink, setCreateLink] = useState<{ title: string; x: number; y: number } | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const keyHandler = useRef<((event: KeyboardEvent) => boolean) | null>(null);
  const dismissedAtRef = useRef<number | null>(null);

  const handleLinkClick = (title: string, coords: { x: number; y: number }) => {
    const normalized = title.split('#', 1)[0].toLowerCase();
    const targetByPath = pagesRef.current.find(
      (candidate) => vaultPath(pagesRef.current, candidate.id).toLowerCase() === normalized,
    );
    const matches = pagesRef.current.filter((candidate) => candidate.title.toLowerCase() === normalized);
    const target = targetByPath ?? (matches.length === 1 ? matches[0] : undefined);
    if (target) {
      navigate(`/w/${workspace.slug}/p/${target.id}`);
      return;
    }
    void pageApi.resolveNode(workspace.id, title).then((resolved) => {
      if (resolved) navigate(`/w/${workspace.slug}/p/${resolved.id}`);
      else setCreateLink({ title, ...coords });
    });
  };
  const linkClickRef = useRef(handleLinkClick);
  linkClickRef.current = handleLinkClick;

  const editor = useEditor({
    editable,
    content: initialDraft.draft.editorDoc,
    onCreate: ({ editor: current }) => {
      if (!initialDraft.restored) {
        // TipTap may normalize an empty document during creation. Treat that
        // normalized shape as the clean baseline instead of showing a false
        // "unsaved" state on every newly opened page.
        savedDocumentRef.current = JSON.stringify(current.getJSON());
        setStatus('saved');
      }
    },
    onUpdate: ({ editor: current }) => {
      if (!editable) return;
      const editorDoc = current.getJSON();
      if (JSON.stringify(editorDoc) === savedDocumentRef.current) {
        localStorage.removeItem(draftKey(page.id));
        setStatus('saved');
        return;
      }
      setStatus('dirty');
      const draft: Draft = {
        baseRevision: savedRevisionRef.current,
        baseMarkdown: baseMarkdownRef.current,
        editorDoc,
      };
      localStorage.setItem(draftKey(page.id), JSON.stringify(draft));
    },
    editorProps: {
      handlePaste: (view, event) => {
        const files = imageFiles(event.clipboardData);
        if (files.length === 0) return false;
        if (!view.editable || !config.file_uploads_enabled) {
          event.preventDefault();
          setImageUploadError(true);
          return true;
        }
        event.preventDefault();
        uploadImages(view, files, view.state.selection.to);
        return true;
      },
      handleDrop: (view, event, _slice, moved) => {
        if (moved) return false;
        const files = imageFiles(event.dataTransfer);
        if (files.length === 0) return false;
        if (!view.editable || !config.file_uploads_enabled) {
          event.preventDefault();
          setImageUploadError(true);
          return true;
        }
        event.preventDefault();
        const coords = view.posAtCoords({ left: event.clientX, top: event.clientY });
        uploadImages(view, files, coords?.pos ?? view.state.selection.to);
        return true;
      },
    },
    extensions: [
      StarterKit.configure({ codeBlock: false, dropcursor: { color: 'rgb(99 102 241)', width: 2 } }),
      CopyableCodeBlock,
      ColoredTextStyle,
      Link.configure({ openOnClick: true, HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer' } }),
      Image.configure({ inline: true }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({ placeholder: 'Write something, or type [[ to link another page…' }),
      Wikilinks.configure({
        onLinkClick: (title, coords) => linkClickRef.current(title, coords),
        onAutocomplete: (next) => {
          if (next && dismissedAtRef.current === next.from) return setAutocomplete(null);
          if (!next) dismissedAtRef.current = null;
          setAutocomplete(next);
        },
        keyHandler,
      }),
    ],
  });

  function uploadImages(view: EditorView, files: File[], pos: number) {
    setImageUploadError(false);
    setImageUploads((count) => count + files.length);
    void insertImagesAt(view, page.id, files, pos)
      .then(({ failed }) => failed && setImageUploadError(true))
      .catch(() => setImageUploadError(true))
      .finally(() => setImageUploads((count) => Math.max(0, count - files.length)));
  }

  async function saveDocument(contentMd?: string, revision = savedRevisionRef.current) {
    if (!editor || status === 'saving') return;
    setStatus('saving');
    try {
      const saved = await pageApi.saveContent(page.id, {
        base_revision: revision,
        ...(contentMd === undefined ? { editor_doc: editor.getJSON() } : { content_md: contentMd }),
      });
      savedRevisionRef.current = saved.content_revision;
      baseMarkdownRef.current = saved.content_md;
      savedDocumentRef.current = JSON.stringify(saved.editor_doc);
      localStorage.removeItem(draftKey(page.id));
      editor.commands.setContent(saved.editor_doc, false);
      setConflict(null);
      setStatus('saved');
      onSaved(saved);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && error.data) {
        setConflict(error.data as unknown as ContentConflict);
        setStatus('dirty');
      } else {
        setStatus('error');
      }
    }
  }

  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (status === 'dirty' || status === 'error') void saveDocument();
      }
    };
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (status !== 'dirty' && status !== 'error') return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('beforeunload', beforeUnload);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('beforeunload', beforeUnload);
    };
  });


  const labels: Record<SaveStatus, string> = {
    saved: '已儲存', dirty: '尚未儲存', saving: '儲存中…', error: '儲存失敗',
  };

  return (
    <div>
      <div className="mb-3 flex h-7 items-center justify-between">
        <span className="text-xs text-neutral-500">標準模式 · {labels[status]}</span>
        <div className="flex items-center gap-3">
          {imageUploads > 0 && <span className="text-[11px] text-neutral-500">上傳圖片中…</span>}
          {imageUploadError && imageUploads === 0 && (
            <span className="text-[11px] text-red-600">
              {config.file_uploads_enabled ? '圖片上傳失敗。' : '此部署已關閉附件上傳。'}
            </span>
          )}
          {editable && (
            <Button
              size="sm"
              variant="primary"
              busy={status === 'saving'}
              disabled={status === 'saved'}
              onClick={() => void saveDocument()}
            >
              儲存 Ctrl+S
            </Button>
          )}
        </div>
      </div>
      <div
        className="km-editor relative"
        onContextMenu={(event) => {
          if (!editor || !editable || editor.state.selection.empty) return;
          if (event.target instanceof Element && event.target.closest('img')) return;
          event.preventDefault();
          setContextMenu({ x: event.clientX, y: event.clientY });
        }}
      >
        <EditorContent editor={editor} />
        {editor && editable && <BlockDragHandle editor={editor} />}
      </div>
      {contextMenu && editor && <SelectionMenu editor={editor} pos={contextMenu} onClose={() => setContextMenu(null)} />}
      {autocomplete && editor && (
        <WikilinkSuggest
          state={autocomplete}
          pages={pages}
          keyHandler={keyHandler}
          onPick={(target) => {
            editor.chain().focus().insertContentAt(
              { from: autocomplete.from, to: autocomplete.to },
              `${vaultPath(pages, target.id)}]]`,
            ).run();
            setAutocomplete(null);
          }}
          onDismiss={() => {
            dismissedAtRef.current = autocomplete.from;
            setAutocomplete(null);
          }}
        />
      )}
      {createLink && (
        <CreateLinkPopover
          title={createLink.title}
          x={createLink.x}
          y={createLink.y}
          busy={createPage.isPending}
          onCreate={() => createPage.mutate(
            { title: createLink.title },
            { onSuccess: (created) => navigate(`/w/${workspace.slug}/p/${created.id}`) },
          )}
          onCancel={() => setCreateLink(null)}
        />
      )}
      {conflict && (
        <ConflictResolver
          key={conflict.current_revision}
          base={baseMarkdownRef.current}
          conflict={conflict}
          busy={status === 'saving'}
          onSave={(resolved) => void saveDocument(resolved, conflict.current_revision)}
          onCancel={() => setConflict(null)}
        />
      )}
    </div>
  );
}
