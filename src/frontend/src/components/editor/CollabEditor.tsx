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
import Collaboration from '@tiptap/extension-collaboration';
import CollaborationCursor from '@tiptap/extension-collaboration-cursor';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import type { EditorView } from '@tiptap/pm/view';
import { ShieldAlert } from 'lucide-react';
import type { Page, User, Workspace } from '../../api/types';
import { pageApi } from '../../api/endpoints';
import { useCreatePage } from '../../hooks/mutations';
import { colorForUser } from '../../lib/color';
import {
  COLLAB_RECONNECT_MAX_MS,
  COLLAB_STABLE_CONNECTION_MS,
  collabReconnectDelayMs,
} from '../../lib/collabReconnect';
import { vaultPath } from '../../lib/tree';
import { Wikilinks, type WikilinkAutocompleteState } from './wikilinks';
import WikilinkSuggest from './WikilinkSuggest';
import CreateLinkPopover from './CreateLinkPopover';
import SelectionMenu from './SelectionMenu';
import BlockDragHandle from './BlockDragHandle';
import { ColoredTextStyle, CopyableCodeBlock } from './editorExtensions';

interface ImageInsertResult {
  uploaded: number;
  failed: number;
}

export function findImageAt(view: EditorView, src: string): { pos: number; attrs: Record<string, unknown> } | null {
  let match: { pos: number; attrs: Record<string, unknown> } | null = null;
  view.state.doc.descendants((node, pos) => {
    if (!match && node.type === view.state.schema.nodes.image && node.attrs.src === src) {
      match = { pos, attrs: node.attrs as Record<string, unknown> };
      return false;
    }
    return true;
  });
  return match;
}

function replacePendingImage(view: EditorView, localSrc: string, remoteSrc: string) {
  if (view.isDestroyed) return;
  const match = findImageAt(view, localSrc);
  if (!match) return;
  view.dispatch(
    view.state.tr.setNodeMarkup(match.pos, undefined, { ...match.attrs, src: remoteSrc }),
  );
}

function removePendingImage(view: EditorView, localSrc: string) {
  if (view.isDestroyed) return;
  const match = findImageAt(view, localSrc);
  if (!match) return;
  const node = view.state.doc.nodeAt(match.pos);
  if (node) view.dispatch(view.state.tr.delete(match.pos, match.pos + node.nodeSize));
}

/** Insert local previews immediately, then replace them with committed attachment URLs. */
export async function insertImagesAt(
  view: EditorView,
  pageId: string,
  files: File[],
  pos: number,
): Promise<ImageInsertResult> {
  let insertAt = pos;
  const pending = files.map((file) => ({ file, localSrc: URL.createObjectURL(file) }));
  let transaction = view.state.tr;
  for (const { file, localSrc } of pending) {
    const node = view.state.schema.nodes.image.create({ src: localSrc, alt: file.name });
    const at = Math.min(insertAt, transaction.doc.content.size);
    transaction = transaction.insert(at, node);
    insertAt = at + node.nodeSize;
  }
  if (transaction.docChanged) view.dispatch(transaction);

  const results = await Promise.allSettled(
    pending.map(async ({ file, localSrc }) => {
      try {
        const att = await pageApi.uploadAttachment(pageId, file);
        replacePendingImage(view, localSrc, att.preview_url ?? att.url);
      } catch (err) {
        removePendingImage(view, localSrc);
        throw err;
      } finally {
        URL.revokeObjectURL(localSrc);
      }
    }),
  );
  for (const result of results) {
    if (result.status === 'rejected') console.error('Image upload failed:', result.reason);
  }
  const failed = results.filter((result) => result.status === 'rejected').length;
  return { uploaded: results.length - failed, failed };
}

export function imageFiles(list: DataTransfer | null): File[] {
  return Array.from(list?.files ?? []).filter((f) => f.type.startsWith('image/'));
}
import { ConnectionIndicator, PresenceAvatars, type CollabStatus, type PeerUser } from './indicators';

interface Props {
  pageId: string;
  workspace: Workspace;
  user: User;
  pages: Page[];
  editable: boolean;
  fileUploadsEnabled: boolean;
}

/** Mount with key={pageId}: the Yjs doc + provider live for exactly one page visit. */
export default function CollabEditor({
  pageId, workspace, user, pages, editable, fileUploadsEnabled,
}: Props) {
  const navigate = useNavigate();
  const createPage = useCreatePage(workspace.id);

  const [status, setStatus] = useState<CollabStatus>('connecting');
  const [forbidden, setForbidden] = useState(false);
  const [peers, setPeers] = useState<PeerUser[]>([]);
  const [imageUploads, setImageUploads] = useState(0);
  const [imageUploadError, setImageUploadError] = useState(false);
  const [autocomplete, setAutocomplete] = useState<WikilinkAutocompleteState | null>(null);
  const [createLink, setCreateLink] = useState<{ title: string; x: number; y: number } | null>(
    null,
  );
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);

  const keyHandler = useRef<((event: KeyboardEvent) => boolean) | null>(null);
  const dismissedAtRef = useRef<number | null>(null);
  const pagesRef = useRef(pages);
  pagesRef.current = pages;

  const [{ ydoc, provider }] = useState(() => {
    const doc = new Y.Doc();
    const wsBase = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/collab`;
    return {
      ydoc: doc,
      provider: new WebsocketProvider(wsBase, pageId, doc, {
        // This remains a fallback for handshake failures. Short-lived
        // successful connections are handled by the stability-aware policy
        // below because y-websocket resets its own counter on every HTTP 101.
        maxBackoffTime: COLLAB_RECONNECT_MAX_MS,
      }),
    };
  });

  useEffect(() => {
    let stopped = false;
    let connectedAt: number | null = null;
    let consecutiveFailures = 0;
    let reconnectPending = false;
    let reconnectTimer: number | null = null;
    let stableTimer: number | null = null;

    const clearReconnectTimer = () => {
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    };
    const clearStableTimer = () => {
      if (stableTimer !== null) window.clearTimeout(stableTimer);
      stableTimer = null;
    };
    const scheduleReconnect = (): number | null => {
      if (stopped || !reconnectPending || reconnectTimer !== null || !navigator.onLine) {
        return null;
      }
      const delayMs = collabReconnectDelayMs(Math.max(1, consecutiveFailures));
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        if (stopped || !reconnectPending) return;
        if (!navigator.onLine) return; // the online event will schedule another attempt
        reconnectPending = false;
        provider.connect();
      }, delayMs);
      return delayMs;
    };

    const onStatus = ({ status: next }: { status: CollabStatus }) => {
      if (next === 'connected') {
        connectedAt = performance.now();
        reconnectPending = false;
        clearReconnectTimer();
        clearStableTimer();
        stableTimer = window.setTimeout(() => {
          // A 101 alone is not success. Only a connection that survives the
          // y-websocket receive-watchdog window resets the failure history.
          consecutiveFailures = 0;
          stableTimer = null;
        }, COLLAB_STABLE_CONNECTION_MS);
      }
      setStatus(next);
    };
    const onClose = (event: CloseEvent | null) => {
      const lifetimeMs = connectedAt === null ? null : Math.round(performance.now() - connectedAt);
      connectedAt = null;
      clearStableTimer();

      if (event?.code === 4401) {
        provider.shouldConnect = false;
        reconnectPending = false;
        clearReconnectTimer();
        queueMicrotask(() => provider.disconnect());
        navigate('/login');
        return;
      }
      if (event?.code === 4403) {
        provider.shouldConnect = false;
        reconnectPending = false;
        clearReconnectTimer();
        queueMicrotask(() => provider.disconnect());
        setForbidden(true);
        return;
      }

      if (lifetimeMs === null || lifetimeMs < COLLAB_STABLE_CONNECTION_MS) {
        consecutiveFailures += 1;
      } else {
        consecutiveFailures = 1;
      }

      // Stop y-websocket's built-in retry before it is scheduled by its close
      // handler. It resets its failure counter on every successful 101, which
      // otherwise causes a tight loop when a proxy closes the socket seconds
      // after opening it.
      provider.shouldConnect = false;
      reconnectPending = true;
      const reconnectDelayMs = scheduleReconnect();
      console.warn('[collab] websocket closed', {
        pageId,
        code: event?.code ?? null,
        reason: event?.reason || null,
        wasClean: event?.wasClean ?? null,
        lifetimeMs,
        consecutiveFailures,
        reconnectDelayMs,
      });
    };
    const onOnline = () => {
      if (!reconnectPending) return;
      const reconnectDelayMs = scheduleReconnect();
      console.info('[collab] network online; reconnect scheduled', {
        pageId,
        consecutiveFailures,
        reconnectDelayMs,
      });
    };
    const awareness = provider.awareness;
    const onAwareness = () => {
      const next: PeerUser[] = [];
      awareness.getStates().forEach((state, clientId) => {
        if (clientId === awareness.clientID) return;
        const u = (state as { user?: { name?: string; color?: string } }).user;
        if (u?.name && u.color) next.push({ clientId, name: u.name, color: u.color });
      });
      setPeers(next);
    };

    provider.on('status', onStatus);
    provider.on('connection-close', onClose);
    awareness.on('change', onAwareness);
    window.addEventListener('online', onOnline);
    onAwareness();

    return () => {
      stopped = true;
      clearReconnectTimer();
      clearStableTimer();
      provider.off('status', onStatus);
      provider.off('connection-close', onClose);
      awareness.off('change', onAwareness);
      window.removeEventListener('online', onOnline);
      provider.destroy();
      ydoc.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLinkClick = (title: string, coords: { x: number; y: number }) => {
    const normalized = title.split('#', 1)[0].toLowerCase();
    const targetByPath = pagesRef.current.find(
      (p) => vaultPath(pagesRef.current, p.id).toLowerCase() === normalized,
    );
    const basenameMatches = pagesRef.current.filter((p) => p.title.toLowerCase() === normalized);
    const target = targetByPath ?? (basenameMatches.length === 1 ? basenameMatches[0] : undefined);
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

  const handleAutocomplete = (state: WikilinkAutocompleteState | null) => {
    if (state && dismissedAtRef.current === state.from) {
      setAutocomplete(null);
      return;
    }
    if (!state) dismissedAtRef.current = null;
    setAutocomplete(state);
  };
  const autocompleteRef = useRef(handleAutocomplete);
  autocompleteRef.current = handleAutocomplete;

  const uploadImages = (view: EditorView, files: File[], pos: number) => {
    setImageUploadError(false);
    setImageUploads((count) => count + files.length);
    void insertImagesAt(view, pageId, files, pos)
      .then(({ failed }) => {
        if (failed) setImageUploadError(true);
      })
      .catch((err) => {
        console.error('Image upload failed:', err);
        setImageUploadError(true);
      })
      .finally(() => setImageUploads((count) => Math.max(0, count - files.length)));
  };

  const editor = useEditor({
    editable,
    editorProps: {
      // Paste/drop images: upload as page attachments, insert served URLs so
      // the markdown keeps a stable /api/v1/attachments/... reference.
      handlePaste: (view, event) => {
        const files = imageFiles(event.clipboardData);
        if (files.length === 0) return false;
        if (!view.editable || !fileUploadsEnabled) {
          event.preventDefault();
          setImageUploadError(true);
          return true;
        }
        event.preventDefault();
        uploadImages(view, files, view.state.selection.to);
        return true;
      },
      handleDrop: (view, event, _slice, moved) => {
        if (moved) return false; // internal block drag — let ProseMirror move it
        const files = imageFiles(event.dataTransfer);
        if (files.length === 0) return false;
        if (!view.editable || !fileUploadsEnabled) {
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
      StarterKit.configure({
        history: false,
        codeBlock: false,
        dropcursor: { color: 'rgb(99 102 241)', width: 2 },
      }),
      CopyableCodeBlock,
      ColoredTextStyle,
      Link.configure({
        openOnClick: true,
        HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer' },
      }),
      Image.configure({ inline: true }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({
        placeholder: 'Write something, or type [[ to link another page…',
      }),
      Collaboration.configure({ document: ydoc, field: 'default' }),
      CollaborationCursor.configure({
        provider,
        user: { name: user.name, color: colorForUser(user.id) },
      }),
      Wikilinks.configure({
        onLinkClick: (title, coords) => linkClickRef.current(title, coords),
        onAutocomplete: (state) => autocompleteRef.current(state),
        keyHandler,
      }),
    ],
  });

  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);

  const pickSuggestion = (target: Page) => {
    if (!editor || !autocomplete) return;
    const targetPath = vaultPath(pages, target.id);
    editor
      .chain()
      .focus()
      .insertContentAt({ from: autocomplete.from, to: autocomplete.to }, `${targetPath}]]`)
      .run();
    setAutocomplete(null);
  };

  if (forbidden) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
        <ShieldAlert size={16} className="flex-none" />
        You no longer have access to edit this page.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex h-7 items-center justify-between">
        <ConnectionIndicator status={status} />
        <div className="flex items-center gap-3">
          {imageUploads > 0 && (
            <span className="text-[11px] text-neutral-500">Uploading {imageUploads} image…</span>
          )}
          {imageUploadError && imageUploads === 0 && (
            <span className="text-[11px] text-red-600">
              {fileUploadsEnabled ? 'Image upload failed. Please paste again.' : 'File uploads are disabled.'}
            </span>
          )}
          <PresenceAvatars peers={peers} />
        </div>
      </div>
      <div
        className="km-editor relative"
        onContextMenu={(e) => {
          if (e.target instanceof Element && e.target.closest('img')) {
            setContextMenu(null);
            return;
          }
          // Custom formatting menu only when text is selected; otherwise keep
          // the native menu (spellcheck, paste, …).
          if (!editor || !editable || editor.state.selection.empty) return;
          e.preventDefault();
          setContextMenu({ x: e.clientX, y: e.clientY });
        }}
      >
        <EditorContent editor={editor} />
        {editor && editable && <BlockDragHandle editor={editor} />}
      </div>
      {contextMenu && editor && (
        <SelectionMenu editor={editor} pos={contextMenu} onClose={() => setContextMenu(null)} />
      )}
      {autocomplete && editor && (
        <WikilinkSuggest
          state={autocomplete}
          pages={pages}
          keyHandler={keyHandler}
          onPick={pickSuggestion}
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
          onCreate={() => {
            createPage.mutate(
              { title: createLink.title },
              {
                onSuccess: (page) => {
                  setCreateLink(null);
                  navigate(`/w/${workspace.slug}/p/${page.id}`);
                },
              },
            );
          }}
          onCancel={() => setCreateLink(null)}
        />
      )}
    </div>
  );
}
