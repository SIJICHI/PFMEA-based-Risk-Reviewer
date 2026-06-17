function hasBareFenceClosingPair(content: string, fenceEnd: number): boolean {
  const FENCE = '```';
  const nextNewline = content.indexOf('\n', fenceEnd);
  if (nextNewline === -1) return false;

  let j = nextNewline + 1;
  let depth = 0;

  while (j < content.length) {
    const idx = content.indexOf(FENCE, j);
    if (idx === -1) return false;

    const isAtLineStart = idx === 0 || content[idx - 1] === '\n';
    if (!isAtLineStart) {
      j = idx + FENCE.length;
      continue;
    }

    const afterFence = content.slice(idx + FENCE.length);
    const hasLang = /^[a-zA-Z]/.test(afterFence);

    if (hasLang) {
      depth++;
    } else if (depth > 0) {
      depth--;
    } else {
      return true;
    }

    j = idx + FENCE.length;
  }

  return false;
}

/**
 * Unwraps markdown code blocks from the given content.
 * @param content - The content to unwrap.
 * @returns The unwrapped content.
 */
export function unwrapMarkdownCodeBlocks(content: string): string {
  const MARKDOWN_OPEN = '```markdown\n';
  const FENCE = '```';

  if (!content.includes(MARKDOWN_OPEN)) {
    return content;
  }

  let result = '';
  let pos = 0;

  while (pos < content.length) {
    const openIdx = content.indexOf(MARKDOWN_OPEN, pos);

    if (openIdx === -1) {
      result += content.slice(pos);
      break;
    }

    result += content.slice(pos, openIdx);

    const contentStart = openIdx + MARKDOWN_OPEN.length;
    let nestingDepth = 0;
    let i = contentStart;
    let closeIdx = -1;

    while (i < content.length) {
      const fenceIdx = content.indexOf(FENCE, i);
      if (fenceIdx === -1) break;

      const isAtLineStart = fenceIdx === 0 || content[fenceIdx - 1] === '\n';

      if (!isAtLineStart) {
        i = fenceIdx + FENCE.length;
        continue;
      }

      const afterFence = content.slice(fenceIdx + FENCE.length);
      const hasLanguageTag = /^[a-zA-Z]/.test(afterFence);

      if (hasLanguageTag) {
        nestingDepth++;
        i = fenceIdx + FENCE.length;
      } else if (nestingDepth > 0) {
        nestingDepth--;
        i = fenceIdx + FENCE.length;
      } else if (hasBareFenceClosingPair(content, fenceIdx + FENCE.length)) {
        nestingDepth++;
        i = fenceIdx + FENCE.length;
      } else {
        closeIdx = fenceIdx;
        break;
      }
    }

    const extractedContent =
      closeIdx !== -1 ? content.slice(contentStart, closeIdx) : content.slice(contentStart);

    result += '\n\n' + extractedContent + '\n\n';

    if (closeIdx !== -1) {
      pos = closeIdx + FENCE.length;
      if (content[pos] === '\n') {
        pos++;
      }
    } else {
      pos = content.length;
    }
  }

  return result;
}
