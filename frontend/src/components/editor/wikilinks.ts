import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import type { EditorView } from '@tiptap/pm/view';
import type { Node as PmNode } from '@tiptap/pm/model';

const WIKILINK_RE = /\[\[([^[\]]+)\]\]/g;

export interface WikilinkAutocompleteState {
  /** Text typed after `[[` so far. */
  query: string;
  /** Document position where the query starts (right after `[[`). */
  from: number;
  /** Current cursor position. */
  to: number;
  /** Viewport coordinates for the popup. */
  left: number;
  bottom: number;
}

export interface WikilinkOptions {
  onLinkClick: (title: string, coords: { x: number; y: number }) => void;
  onAutocomplete: (state: WikilinkAutocompleteState | null) => void;
  /** Bridge for the React popup to intercept editor key events while open. */
  keyHandler: { current: ((event: KeyboardEvent) => boolean) | null };
}

function buildDecorations(doc: PmNode): DecorationSet {
  const decorations: Decoration[] = [];
  doc.descendants((node, pos) => {
    if (!node.isText || !node.text) return;
    for (const match of node.text.matchAll(WIKILINK_RE)) {
      const index = match.index ?? 0;
      const from = pos + index;
      const to = from + match[0].length;
      decorations.push(
        Decoration.inline(from, to, {
          class: 'wikilink',
          'data-wikilink': match[1],
        }),
      );
    }
  });
  return DecorationSet.create(doc, decorations);
}

function detectAutocomplete(view: EditorView): WikilinkAutocompleteState | null {
  const { selection } = view.state;
  if (!selection.empty) return null;
  const { $from } = selection;
  if (!$from.parent.isTextblock) return null;

  const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '￼');
  const match = /\[\[([^[\]]*)$/.exec(textBefore);
  if (!match) return null;

  const query = match[1];
  const from = $from.pos - query.length;
  let coords;
  try {
    coords = view.coordsAtPos(from);
  } catch {
    return null;
  }
  return { query, from, to: $from.pos, left: coords.left, bottom: coords.bottom };
}

export const Wikilinks = Extension.create<WikilinkOptions>({
  name: 'wikilinks',

  addOptions() {
    return {
      onLinkClick: () => undefined,
      onAutocomplete: () => undefined,
      keyHandler: { current: null },
    };
  },

  addProseMirrorPlugins() {
    const options = this.options;

    const decorationPlugin = new Plugin({
      key: new PluginKey('wikilink-decorations'),
      state: {
        init: (_config, state) => buildDecorations(state.doc),
        apply: (tr, old) => (tr.docChanged ? buildDecorations(tr.doc) : old.map(tr.mapping, tr.doc)),
      },
      props: {
        decorations(state) {
          return this.getState(state);
        },
        handleDOMEvents: {
          mousedown: (_view, event) => {
            const target = event.target as HTMLElement | null;
            const el = target?.closest?.('[data-wikilink]');
            if (el instanceof HTMLElement && el.dataset.wikilink) {
              event.preventDefault();
              options.onLinkClick(el.dataset.wikilink, { x: event.clientX, y: event.clientY });
              return true;
            }
            return false;
          },
        },
        handleKeyDown: (_view, event) => options.keyHandler.current?.(event) ?? false,
      },
    });

    const autocompletePlugin = new Plugin({
      key: new PluginKey('wikilink-autocomplete'),
      view: () => ({
        update: (view) => {
          options.onAutocomplete(detectAutocomplete(view));
        },
        destroy: () => {
          options.onAutocomplete(null);
        },
      }),
    });

    return [decorationPlugin, autocompletePlugin];
  },
});
