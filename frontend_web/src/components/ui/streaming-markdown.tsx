'use client';

import { useMemo } from 'react';
import { SquareArrowOutUpRight } from 'lucide-react';
import {
  Streamdown,
  type Components,
  type ThemeInput,
  type StreamdownProps,
  type PluginConfig,
  type ControlsConfig,
} from 'streamdown';
import { createCodePlugin } from '@streamdown/code';
import { createMathPlugin } from '@streamdown/math';
import { cn } from '@/lib/utils';
import { unwrapMarkdownCodeBlocks } from '@/lib/unwrap-markdown-code-blocks';
import { Heading } from '@/components/ui/heading';

// これらの見出しを持つ列は表内で厳密に等幅にする（リスク低減アクション表の
// 「主な要因／現在の管理／推奨アクション」を想定）。他の見出しの列は内容に応じた幅。
const EQUAL_WIDTH_HEADERS = ['主な要因', '現在の管理', '推奨アクション'];

type HastNode = {
  type?: string;
  value?: string;
  tagName?: string;
  children?: HastNode[];
};

function hastText(node: HastNode | undefined): string {
  if (!node) return '';
  if (node.type === 'text') return node.value ?? '';
  return (node.children ?? []).map(hastText).join('');
}

// テーブルの hast ノードから、ヘッダ文字列と各列の最大文字数を取得する。
function getTableInfo(node: HastNode | undefined): {
  headerCells: string[];
  colMax: number[];
} {
  const headerCells: string[] = [];
  const colMax: number[] = [];
  if (!node?.children) return { headerCells, colMax };

  const walkRow = (tr: HastNode, isHeader: boolean): void => {
    let ci = 0;
    for (const cell of tr.children ?? []) {
      if (cell.tagName !== 'th' && cell.tagName !== 'td') continue;
      const text = hastText(cell).trim();
      colMax[ci] = Math.max(colMax[ci] ?? 0, text.length);
      if (isHeader) headerCells[ci] = text;
      ci += 1;
    }
  };

  for (const section of node.children) {
    if (section.tagName === 'thead') {
      for (const tr of section.children ?? []) {
        if (tr.tagName === 'tr') walkRow(tr, true);
      }
    } else if (section.tagName === 'tbody') {
      for (const tr of section.children ?? []) {
        if (tr.tagName === 'tr') walkRow(tr, false);
      }
    } else if (section.tagName === 'tr') {
      walkRow(section, headerCells.length === 0);
    }
  }
  return { headerCells, colMax };
}

// 等幅対象の列が2つ以上あれば、colgroup 用の列幅配列を返す（無ければ null）。
// 等幅列は「残り幅 ÷ 等幅列数」の calc で厳密に同一幅。それ以外の列は内容量に
// 応じた固定幅（4〜18文字 + 余白）で、画面幅内に収める（横スクロールを避ける）。
function buildColWidths(headerCells: string[], colMax: number[]): string[] | null {
  const equalIdx = headerCells
    .map((h, i) => (EQUAL_WIDTH_HEADERS.includes(h) ? i : -1))
    .filter((i) => i >= 0);
  if (equalIdx.length < 2) return null;

  const narrowCh = colMax.map((len, i) =>
    equalIdx.includes(i) ? 0 : Math.min(Math.max(len || 4, 4), 18) + 2
  );
  const sumNarrow = narrowCh.reduce((a, b) => a + b, 0);
  const equalWidth = `calc((100% - ${sumNarrow}ch) / ${equalIdx.length})`;
  return colMax.map((_, i) =>
    equalIdx.includes(i) ? equalWidth : `${narrowCh[i]}ch`
  );
}

/* eslint-disable @typescript-eslint/no-unused-vars */
export const MARKDOWN_COMPONENTS: Components = {
  ul: ({ children, node, ...props }) => (
    <ul className="my-4 list-disc pl-8 leading-relaxed" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, node, ...props }) => (
    <ol className="my-4 list-decimal pl-8 leading-relaxed" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, node, ...props }) => (
    <li className="my-1" {...props}>
      {children}
    </li>
  ),
  h1: ({ children, node, ...props }) => (
    <Heading level={2} className="mt-6 mb-4" {...props}>
      {children}
    </Heading>
  ),
  h2: ({ children, node, ...props }) => (
    <Heading level={3} className="mt-6 mb-4" {...props}>
      {children}
    </Heading>
  ),
  h3: ({ children, node, ...props }) => (
    <Heading level={4} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  h4: ({ children, node, ...props }) => (
    <Heading level={5} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  h5: ({ children, node, ...props }) => (
    <Heading level={6} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  p: ({ children, node, ...props }) => (
    <p className="body leading-relaxed" {...props}>
      {children}
    </p>
  ),
  hr: ({ node, ...props }) => <hr className="mt-4 mb-2" {...props} />,
  table: ({ children, className, node, ...props }) => {
    const { headerCells, colMax } = getTableInfo(node as unknown as HastNode);
    const colWidths = buildColWidths(headerCells, colMax);
    return (
      <div className="my-2 flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
        <table
          className={cn(
            'h-fit w-full border-separate border-spacing-0 overflow-auto rounded-lg',
            colWidths ? 'table-fixed' : 'table-auto',
            '[&_th:nth-child(2)]:whitespace-nowrap [&_td:nth-child(2)]:whitespace-nowrap',
            className
          )}
          {...props}
        >
          {colWidths && (
            <colgroup>
              {colWidths.map((w, i) => (
                <col key={i} style={{ width: w }} />
              ))}
            </colgroup>
          )}
          {children}
        </table>
      </div>
    );
  },
  thead: ({ children, className, node, ...props }) => (
    <thead
      className={cn(
        'border-sidebar-border bg-background p-0 font-normal text-secondary-foreground',
        className
      )}
      {...props}
    >
      {children}
    </thead>
  ),
  th: ({ children, className, node, ...props }) => (
    <th
      className={cn(
        `
          border-r border-b border-border bg-background p-3 pl-2 text-left font-normal text-secondary-foreground
          last:border-r-0
        `,
        className
      )}
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, className, node, ...props }) => (
    <td
      className={cn(
        `
          border-r border-b border-border bg-background p-3 pl-2 text-left leading-5 align-top whitespace-normal
          break-words
          last:border-r-0
          [tr:last-child_&]:border-b-0
        `,
        className
      )}
      {...props}
    >
      {children}
    </td>
  ),
  a: ({ children, node, ...props }) => (
    <a
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center anchor"
      {...props}
    >
      {children}
      <SquareArrowOutUpRight size={18} className="ml-1" />
    </a>
  ),
};
/* eslint-enable @typescript-eslint/no-unused-vars */

const plugins: PluginConfig = {
  code: createCodePlugin({ themes: ['github-light', 'github-dark-dimmed'] }),
  math: createMathPlugin({ singleDollarTextMath: true }),
};

const shikiTheme: [ThemeInput, ThemeInput] = ['github-light', 'github-dark-dimmed'] as const;

const controlsConfig: ControlsConfig = {
  code: {
    copy: true,
    download: false,
  },
  table: false,
};

export function StreamingMarkdown({
  children,
  className,
  unwrapMarkdown = true,
  ...props
}: {
  children: string;
  className?: string;
  unwrapMarkdown?: boolean;
} & Partial<StreamdownProps>) {
  const transformedContent = useMemo(
    () => (unwrapMarkdown ? unwrapMarkdownCodeBlocks(children) : children),
    [children, unwrapMarkdown]
  );

  if (!children) {
    return null;
  }

  return (
    <div className={className}>
      <Streamdown
        plugins={plugins}
        controls={controlsConfig}
        components={MARKDOWN_COMPONENTS}
        shikiTheme={shikiTheme}
        isAnimating={false}
        {...props}
      >
        {transformedContent}
      </Streamdown>
    </div>
  );
}
