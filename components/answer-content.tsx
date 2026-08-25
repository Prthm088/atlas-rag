import { Fragment, type ReactNode } from 'react';

import type { Citation } from '@/lib/types';

const citationTokenPattern = /(\[C\d+(?:\s*,\s*C\d+)*\])/g;
const inlineMarkupPattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g;

type AnswerBlock = {
  kind: 'heading' | 'paragraph' | 'unordered-list' | 'ordered-list';
  content: string[];
};

function renderPlainInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(inlineMarkupPattern).map((part, index) => {
    const key = `${keyPrefix}-inline-${index}`;
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

function renderInline(
  text: string,
  citations: Citation[],
  onCitation: (citation: Citation) => void,
  keyPrefix: string,
): ReactNode[] {
  return text.split(citationTokenPattern).map((part, index) => {
    const labels = [...part.matchAll(/C(\d+)/g)].map((match) => Number(match[1]));
    if (!part.startsWith('[') || !part.endsWith(']') || labels.length === 0) {
      return <Fragment key={`${keyPrefix}-text-${index}`}>{renderPlainInline(part, `${keyPrefix}-${index}`)}</Fragment>;
    }

    return (
      <Fragment key={`${keyPrefix}-citations-${index}`}>
        {labels.map((label) => {
          const citation = citations.find((item) => item.label === label);
          return citation ? (
            <button
              key={`${keyPrefix}-citation-${index}-${label}`}
              className="inline-citation"
              onClick={() => onCitation(citation)}
              aria-label={`Open citation C${label} from ${citation.document_name}`}
              title={`Open ${citation.document_name}`}
              type="button"
            >
              {label}
            </button>
          ) : (
            <span
              key={`${keyPrefix}-citation-${index}-${label}`}
              className="citation-unavailable"
              title="This earlier answer did not save a source link for this marker"
            >
              {label}
            </span>
          );
        })}
      </Fragment>
    );
  });
}

function parseAnswer(content: string): AnswerBlock[] {
  const lines = content.replace(/\r\n?/g, '\n').split('\n');
  const blocks: AnswerBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      blocks.push({ kind: 'heading', content: [heading[1]] });
      index += 1;
      continue;
    }

    const bullet = line.match(/^[-*•]\s+(.+)$/);
    if (bullet) {
      const items: string[] = [];
      while (index < lines.length) {
        const match = lines[index].trim().match(/^[-*•]\s+(.+)$/);
        if (!match) break;
        items.push(match[1]);
        index += 1;
      }
      blocks.push({ kind: 'unordered-list', content: items });
      continue;
    }

    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) {
      const items: string[] = [];
      while (index < lines.length) {
        const match = lines[index].trim().match(/^\d+[.)]\s+(.+)$/);
        if (!match) break;
        items.push(match[1]);
        index += 1;
      }
      blocks.push({ kind: 'ordered-list', content: items });
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const next = lines[index].trim();
      if (!next || /^#{1,3}\s+/.test(next) || /^[-*•]\s+/.test(next) || /^\d+[.)]\s+/.test(next)) break;
      paragraph.push(next);
      index += 1;
    }
    blocks.push({ kind: 'paragraph', content: [paragraph.join(' ')] });
  }

  return blocks;
}

export function citationSummary(content: string, citations: Citation[]): string {
  const sourceCount = new Set(citations.map((citation) => citation.document_id)).size;
  if (sourceCount > 0) return `${sourceCount} cited source${sourceCount === 1 ? '' : 's'}`;
  if (/\[C\d+/.test(content)) return 'Source links unavailable for this earlier answer';
  return 'No citations required';
}

export function AnswerContent({
  content,
  citations,
  onCitation,
}: {
  content: string;
  citations: Citation[];
  onCitation: (citation: Citation) => void;
}) {
  const blocks = parseAnswer(content);
  return (
    <div className="answer-content">
      {blocks.map((block, blockIndex) => {
        const key = `answer-block-${blockIndex}`;
        if (block.kind === 'heading') {
          return <h4 key={key}>{renderInline(block.content[0], citations, onCitation, key)}</h4>;
        }
        if (block.kind === 'unordered-list' || block.kind === 'ordered-list') {
          const List = block.kind === 'unordered-list' ? 'ul' : 'ol';
          return (
            <List key={key}>
              {block.content.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(item, citations, onCitation, `${key}-${itemIndex}`)}</li>
              ))}
            </List>
          );
        }
        return <p key={key}>{renderInline(block.content[0], citations, onCitation, key)}</p>;
      })}
    </div>
  );
}
