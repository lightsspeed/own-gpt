import { Stack, Inline, Surface, Divider, PageContainer } from '@/components/layout';
import { Button, IconButton, Badge, Skeleton, EmptyState, Tooltip, Accordion } from '@/components/primitives';
import { answerModes, answerModeText, answerModeBg, retrievalMethods, pipelineStages } from '@/design-system/ai';
import { semantic } from '@/design-system';

/* ── Section wrapper ── */
function LabSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Surface variant="surface" className="mb-8">
      <Stack gap="lg">
        <h2 className="text-h2 text-text-primary">{title}</h2>
        {children}
      </Stack>
    </Surface>
  );
}

function ColorSwatch({ name, hsl }: { name: string; hsl: string }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-8 w-8 rounded-md shrink-0 border border-border"
        style={{ background: `hsl(${hsl})` }}
      />
      <div>
        <div className="text-small text-text-primary">{name}</div>
        <div className="text-micro text-text-disabled font-mono">{hsl}</div>
      </div>
    </div>
  );
}

function Cat({ children }: { children: React.ReactNode }) {
  return <div className="text-caption text-text-secondary uppercase tracking-wider mb-2 mt-4 first:mt-0">{children}</div>;
}

export function UiLabPage() {
  return (
    <PageContainer className="py-8">
      <Stack gap="xl">
        <div>
          <h1 className="text-display text-text-primary">UI Laboratory</h1>
          <p className="text-body text-text-secondary mt-2">Every component, every state. Design system reference.</p>
        </div>

        {/* ── Colors ── */}
        <LabSection title="Colors">
          <Cat>Surfaces</Cat>
          <Inline gap="lg" wrap>
            <ColorSwatch name="canvas" hsl={semantic.canvas} />
            <ColorSwatch name="surface" hsl={semantic.surface} />
            <ColorSwatch name="elevated" hsl={semantic.elevated} />
            <ColorSwatch name="overlay" hsl={semantic.overlay} />
            <ColorSwatch name="hover" hsl={semantic.hover} />
          </Inline>
          <Cat>Text</Cat>
          <Inline gap="lg" wrap>
            <ColorSwatch name="text-primary" hsl={semantic.text.primary} />
            <ColorSwatch name="text-secondary" hsl={semantic.text.secondary} />
            <ColorSwatch name="text-disabled" hsl={semantic.text.disabled} />
          </Inline>
          <Cat>Functional</Cat>
          <Inline gap="lg" wrap>
            <ColorSwatch name="accent" hsl={semantic.accent} />
            <ColorSwatch name="success" hsl={semantic.success} />
            <ColorSwatch name="warning" hsl={semantic.warning} />
            <ColorSwatch name="danger" hsl={semantic.danger} />
            <ColorSwatch name="info" hsl={semantic.info} />
          </Inline>
        </LabSection>

        {/* ── Typography ── */}
        <LabSection title="Typography">
          <div className="space-y-2">
            <div className="text-display text-text-primary">Display 32</div>
            <div className="text-h1 text-text-primary">Heading 1 28</div>
            <div className="text-h2 text-text-primary">Heading 2 24</div>
            <div className="text-h3 text-text-primary">Heading 3 20</div>
            <div className="text-title text-text-primary">Title 18</div>
            <div className="text-body text-text-primary">Body 15 — The quick brown fox jumps over the lazy dog.</div>
            <div className="text-small text-text-primary">Small 13 — The quick brown fox jumps over the lazy dog.</div>
            <div className="text-caption text-text-secondary">Caption 12 — The quick brown fox jumps.</div>
            <div className="text-micro text-text-disabled">Micro 11 — Quick brown fox.</div>
          </div>
        </LabSection>

        {/* ── Buttons ── */}
        <LabSection title="Buttons">
          <Cat>Variants</Cat>
          <Inline gap="md" wrap>
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">Danger</Button>
          </Inline>
          <Cat>Sizes</Cat>
          <Inline gap="md" wrap>
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
          </Inline>
          <Cat>With icon</Cat>
          <Inline gap="md" wrap>
            <Button icon={<svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>}>With Icon</Button>
            <Button loading>Loading</Button>
          </Inline>
          <Cat>Disabled</Cat>
          <Inline gap="md" wrap>
            <Button disabled>Primary</Button>
            <Button variant="secondary" disabled>Secondary</Button>
            <Button variant="ghost" disabled>Ghost</Button>
          </Inline>
        </LabSection>

        {/* ── Icon Buttons ── */}
        <LabSection title="Icon Buttons">
          <Inline gap="md" wrap>
            <IconButton label="Settings" size="sm"><svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg></IconButton>
            <IconButton label="Close" size="md"><svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg></IconButton>
            <IconButton label="Delete" size="lg" variant="danger"><svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg></IconButton>
          </Inline>
        </LabSection>

        {/* ── Badges ── */}
        <LabSection title="Badges">
          <Cat>Variants</Cat>
          <Inline gap="md" wrap>
            <Badge variant="default">Default</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="danger">Danger</Badge>
            <Badge variant="info">Info</Badge>
          </Inline>
          <Cat>With dot</Cat>
          <Inline gap="md" wrap>
            <Badge variant="success" dot>Online</Badge>
            <Badge variant="warning" dot>Pending</Badge>
            <Badge variant="danger" dot>Offline</Badge>
          </Inline>
          <Cat>Answer modes</Cat>
          <Inline gap="md" wrap>
            {(Object.entries(answerModes) as [string, typeof answerModes.grounded][]).map(([key, mode]) => (
              <Badge key={key} variant={key as any}>{mode.label}</Badge>
            ))}
          </Inline>
        </LabSection>

        {/* ── AI Answer Mode Badges ── */}
        <LabSection title="Answer Modes (AI tokens)">
          <Inline gap="md" wrap>
            {(Object.entries(answerModes) as [string, typeof answerModes.grounded][]).map(([key, mode]) => (
              <div key={key} className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-small font-medium ${answerModeBg(key as any)} ${answerModeText(key as any)}`}>
                {mode.label}
                <span className="text-micro opacity-70">{retrievalMethods.hybrid.short}</span>
              </div>
            ))}
          </Inline>
        </LabSection>

        {/* ── Pipeline Stages ── */}
        <LabSection title="Pipeline Stages (AI tokens)">
          <Stack gap="sm">
            {(Object.entries(pipelineStages) as [string, typeof pipelineStages.thinking][]).map(([key, stage]) => (
              <Inline key={key} gap="md" align="center">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: `hsl(${stage.color})` }} />
                <span className="text-body text-text-primary">{stage.label}</span>
                <span className="text-micro text-text-disabled">{stage.icon}</span>
              </Inline>
            ))}
          </Stack>
        </LabSection>

        {/* ── Skeleton ── */}
        <LabSection title="Skeleton">
          <Cat>Text</Cat>
          <Stack gap="sm" className="w-64">
            <Skeleton variant="text" />
            <Skeleton variant="text" width="80%" />
            <Skeleton variant="text" width="60%" />
          </Stack>
          <Cat>Circular + Rectangular</Cat>
          <Inline gap="md" align="center">
            <Skeleton variant="circular" />
            <Skeleton variant="rectangular" width={120} height={80} />
          </Inline>
        </LabSection>

        {/* ── Empty State ── */}
        <LabSection title="Empty State">
          <EmptyState
            icon={<svg className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>}
            title="No documents yet"
            description="Upload a PDF, DOCX, or markdown file to get started."
            action={{ label: 'Upload document', onClick: () => {} }}
          />
        </LabSection>

        {/* ── Accordion ── */}
        <LabSection title="Accordion">
          <Accordion
            items={[
              { id: '1', title: 'What is Grounded mode?', content: 'Answer is directly supported by source documents. The model only uses retrieved chunks to generate the response.' },
              { id: '2', title: 'What is Hybrid mode?', content: 'Answer combines retrieved knowledge with model reasoning. Multiple documents may be referenced.' },
              { id: '3', title: 'How are sources ranked?', content: 'Sources are ranked using Reciprocal Rank Fusion (RRF) followed by FlashRank cross-encoder reranking.' },
            ]}
          />
        </LabSection>

        {/* ── Tooltip ── */}
        <LabSection title="Tooltip">
          <Inline gap="lg">
            <Tooltip content="Top tooltip" side="top">
              <Button variant="secondary">Hover top</Button>
            </Tooltip>
            <Tooltip content="Bottom tooltip" side="bottom">
              <Button variant="secondary">Hover bottom</Button>
            </Tooltip>
            <Tooltip content="Left tooltip" side="left">
              <Button variant="secondary">Hover left</Button>
            </Tooltip>
            <Tooltip content="Right tooltip" side="right">
              <Button variant="secondary">Hover right</Button>
            </Tooltip>
          </Inline>
        </LabSection>

        {/* ── Surface variants ── */}
        <LabSection title="Surface variants">
          <Inline gap="md" wrap>
            <Surface variant="canvas" padding="md"><span className="text-body text-text-primary">Canvas</span></Surface>
            <Surface variant="surface" padding="md"><span className="text-body text-text-primary">Surface</span></Surface>
            <Surface variant="elevated" padding="md"><span className="text-body text-text-primary">Elevated</span></Surface>
            <Surface variant="glass" padding="md"><span className="text-body text-text-primary">Glass</span></Surface>
          </Inline>
        </LabSection>

        {/* ── Layout demonstrators ── */}
        <LabSection title="Stack + Inline">
          <Cat>Stack (vertical, gap="md")</Cat>
          <Stack gap="md" className="w-48">
            <div className="bg-elevated rounded-lg p-3 text-small text-text-primary">Item 1</div>
            <div className="bg-elevated rounded-lg p-3 text-small text-text-primary">Item 2</div>
            <div className="bg-elevated rounded-lg p-3 text-small text-text-primary">Item 3</div>
          </Stack>
          <Cat>Inline (horizontal, gap="md")</Cat>
          <Inline gap="md">
            <div className="bg-elevated rounded-lg p-3 text-small text-text-primary">A</div>
            <div className="bg-elevated rounded-lg p-3 text-small text-text-primary">B</div>
            <div className="bg-elevated rounded-lg p-3 text-small text-text-primary">C</div>
          </Inline>
        </LabSection>

        {/* ── Divider ── */}
        <LabSection title="Divider">
          <Divider spacing="md" />
        </LabSection>
      </Stack>
    </PageContainer>
  );
}
