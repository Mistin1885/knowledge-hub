import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
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
import { Wikilinks, type WikilinkAutocompleteState } from './wikilinks';
import WikilinkSuggest from './WikilinkSuggest';
import CreateLinkPopover from './CreateLinkPopover';
import SelectionMenu from './SelectionMenu';
import BlockDragHandle from './BlockDragHandle';

/** Upload image files as page attachments and insert image nodes at `pos`. */
async function insertImagesAt(view: EditorView, pageId: string, files: File[], pos: number) {
  let insertAt = pos;
  for (const file of files) {
    try {
      const att = await pageApi.uploadAttachment(pageId, file);
      const { state } = view;
      const node = state.schema.nodes.image.create({ src: att.url, alt: att.filename });
      const at = Math.min(insertAt, state.doc.content.size);
      view.dispatch(state.tr.insert(at, node));
      insertAt = at + node.nodeSize;
    } catch (err) {
      console.error('Image upload failed:', err);
    }
  }
}

function imageFiles(list: DataTransfer | null): File[] {
  return Array.from(list?.files ?? []).filter((f) => f.type.startsWith('image/'));
}
import { ConnectionIndicator, PresenceAvatars, type CollabStatus, type PeerUser } from './indicators';

interface Props {
  pageId: string;
  workspace: Workspace;
  user: User;
  pages: Page[];
  editable: boolean;
}

/** Mount with key={pageId}: the Yjs doc + provider live for exactly one page visit. */
export default function CollabEditor({ pageId, workspace, user, pages, editable }: Props) {
  const navigate = useNavigate();
  const createPage = useCreatePage(workspace.id);

  const [status, setStatus] = useState<CollabStatus>('connecting');
  const [forbidden, setForbidden] = useState(false);
  const [peers, setPeers] = useState<PeerUser[]>([]);
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
    return { ydoc: doc, provider: new WebsocketProvider(wsBase, pageId, doc) };
  });

  useEffect(() => {
    const onStatus = ({ status: next }: { status: CollabStatus }) => setStatus(next);
    const onClose = (event: CloseEvent | null) => {
      if (!event) return;
      if (event.code === 4401) {
        provider.disconnect();
        navigate('/login');
      } else if (event.code === 4403) {
        provider.disconnect();
        setForbidden(true);
      }
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
    onAwareness();

    return () => {
      provider.off('status', onStatus);
      provider.off('connection-close', onClose);
      awareness.off('change', onAwareness);
      provider.destroy();
      ydoc.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLinkClick = (title: string, coords: { x: number; y: number }) => {
    const target = pagesRef.current.find((p) => p.title.toLowerCase() === title.toLowerCase());
    if (target) navigate(`/w/${workspace.slug}/p/${target.id}`);
    else setCreateLink({ title, ...coords });
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

  const editor = useEditor({
    editable,
    editorProps: {
      // Paste/drop images: upload as page attachments, insert served URLs so
      // the markdown keeps a stable /api/v1/attachments/... reference.
      handlePaste: (view, event) => {
        const files = imageFiles(event.clipboardData);
        if (files.length === 0 || !view.editable) return false;
        event.preventDefault();
        void insertImagesAt(view, pageId, files, view.state.selection.to);
        return true;
      },
      handleDrop: (view, event, _slice, moved) => {
        if (moved) return false; // internal block drag — let ProseMirror move it
        const files = imageFiles(event.dataTransfer);
        if (files.length === 0 || !view.editable) return false;
        event.preventDefault();
        const coords = view.posAtCoords({ left: event.clientX, top: event.clientY });
        void insertImagesAt(view, pageId, files, coords?.pos ?? view.state.selection.to);
        return true;
      },
    },
    extensions: [
      StarterKit.configure({
        history: false,
        dropcursor: { color: 'rgb(99 102 241)', width: 2 },
      }),
      Link.configure({ openOnClick: false }),
      Image,
      TaskList,
      TaskItem.configure({ nested: true }),
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

  const pickSuggestion = (title: string) => {
    if (!editor || !autocomplete) return;
    editor
      .chain()
      .focus()
      .insertContentAt({ from: autocomplete.from, to: autocomplete.to }, `${title}]]`)
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
        <PresenceAvatars peers={peers} />
      </div>
      <div
        className="km-editor relative"
        onContextMenu={(e) => {
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
