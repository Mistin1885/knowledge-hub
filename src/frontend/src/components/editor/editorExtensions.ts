import CodeBlock from '@tiptap/extension-code-block';
import TextStyle from '@tiptap/extension-text-style';

const SVG_NS = 'http://www.w3.org/2000/svg';

function copyIcon() {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '15');
  svg.setAttribute('height', '15');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');

  const back = document.createElementNS(SVG_NS, 'rect');
  back.setAttribute('width', '14');
  back.setAttribute('height', '14');
  back.setAttribute('x', '8');
  back.setAttribute('y', '8');
  back.setAttribute('rx', '2');
  back.setAttribute('ry', '2');

  const front = document.createElementNS(SVG_NS, 'path');
  front.setAttribute('d', 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2');
  svg.append(back, front);
  return svg;
}

function checkIcon() {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '15');
  svg.setAttribute('height', '15');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('d', 'm20 6-11 11-5-5');
  svg.append(path);
  return svg;
}

async function writeClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.append(textarea);
  textarea.select();
  document.execCommand('copy');
  textarea.remove();
}

/** Keep the standard codeBlock schema while adding an isolated copy control. */
export const CopyableCodeBlock = CodeBlock.extend({
  addNodeView() {
    return ({ node }) => {
      let currentNode = node;
      let resetTimer: number | undefined;

      const wrapper = document.createElement('div');
      wrapper.className = 'km-code-block';

      const pre = document.createElement('pre');
      const code = document.createElement('code');
      pre.append(code);

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'km-code-copy';
      button.contentEditable = 'false';
      button.setAttribute('aria-label', 'Copy code');
      button.title = 'Copy code';
      button.append(copyIcon());

      const onMouseDown = (event: MouseEvent) => event.preventDefault();
      const onClick = () => {
        void writeClipboard(currentNode.textContent).then(() => {
          window.clearTimeout(resetTimer);
          button.replaceChildren(checkIcon());
          button.setAttribute('aria-label', 'Code copied');
          button.title = 'Copied';
          resetTimer = window.setTimeout(() => {
            button.replaceChildren(copyIcon());
            button.setAttribute('aria-label', 'Copy code');
            button.title = 'Copy code';
          }, 1500);
        });
      };

      button.addEventListener('mousedown', onMouseDown);
      button.addEventListener('click', onClick);
      wrapper.append(pre, button);

      return {
        dom: wrapper,
        contentDOM: code,
        update(updatedNode) {
          if (updatedNode.type !== currentNode.type) return false;
          currentNode = updatedNode;
          return true;
        },
        destroy() {
          window.clearTimeout(resetTimer);
          button.removeEventListener('mousedown', onMouseDown);
          button.removeEventListener('click', onClick);
        },
      };
    };
  },
});

/** Inline style mark restricted by the UI to the small preset palette. */
export const ColoredTextStyle = TextStyle.extend({
  addAttributes() {
    const normalizeColor = (value: string | undefined) => {
      if (!value) return null;
      if (/^#[0-9a-f]{6}$/i.test(value)) return value.toLowerCase();

      const rgb = value.match(/^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/i);
      if (!rgb) return null;
      const channels = rgb.slice(1).map(Number);
      if (channels.some((channel) => channel > 255)) return null;
      return `#${channels.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;
    };

    const styleValue = (element: HTMLElement, property: string) => {
      const style = element.getAttribute('style') ?? '';
      const match = style.match(
        new RegExp(
          `(?:^|;)\\s*${property}\\s*:\\s*(#[0-9a-f]{6}|rgb\\(\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*\\))`,
          'i',
        ),
      );
      return normalizeColor(match?.[1]);
    };

    return {
      color: {
        default: null,
        parseHTML: (element) => styleValue(element, 'color'),
        renderHTML: (attributes) =>
          attributes.color ? { style: `color: ${String(attributes.color)}` } : {},
      },
      backgroundColor: {
        default: null,
        parseHTML: (element) => styleValue(element, 'background-color'),
        renderHTML: (attributes) =>
          attributes.backgroundColor
            ? { style: `background-color: ${String(attributes.backgroundColor)}` }
            : {},
      },
    };
  },
});
