import Link from 'next/link';

const sourceCards = [
  { title: 'Architecture handbook', meta: 'PDF · 42 pages', tone: 'lime' },
  { title: 'Product decisions', meta: 'DOCX · Updated today', tone: 'violet' },
  { title: 'Support playbook', meta: 'Markdown · 18 sections', tone: 'amber' },
];

export default function Home() {
  return (
    <main className="site-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Atlas RAG home">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>Atlas</span>
        </a>
        <nav className="top-actions" aria-label="Account navigation">
          <span className="system-status"><i /> Systems ready</span>
          <Link className="ghost-button" href="/auth">Sign in</Link>
          <Link className="primary-button" href="/auth">Create account</Link>
        </nav>
      </header>

      <section id="top" className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow"><span>Private knowledge, grounded answers</span></p>
          <h1>Your documents.<br />Answers you can <em>verify.</em></h1>
          <p className="hero-lede">
            Upload your knowledge base, ask natural questions, and trace every answer
            back to the exact source—without mixing your data with anyone else’s.
          </p>
          <div className="hero-actions">
            <Link className="primary-button large" href="/auth">Build my library <span>→</span></Link>
            <a href="#workspace">Explore the workspace</a>
          </div>
          <dl className="trust-row">
            <div><dt>Hybrid</dt><dd>semantic + keyword search</dd></div>
            <div><dt>Private</dt><dd>isolated per account</dd></div>
            <div><dt>Cited</dt><dd>evidence with every answer</dd></div>
          </dl>
        </div>

        <div id="workspace" className="workspace-preview" aria-label="Atlas workspace preview">
          <div className="preview-rail">
            <span className="rail-logo">A</span>
            <span className="rail-icon active">⌁</span>
            <span className="rail-icon">▤</span>
            <span className="rail-icon">⌕</span>
            <span className="rail-avatar">RK</span>
          </div>
          <div className="preview-main">
            <div className="preview-head">
              <div><small>Workspace</small><strong>Research library</strong></div>
              <button type="button">＋ Add sources</button>
            </div>
            <div className="question-block">
              <span className="question-label">Ask across 12 sources</span>
              <p>What are the main security decisions, and why were they chosen?</p>
              <button type="button" aria-label="Submit question">↑</button>
            </div>
            <div className="answer-block">
              <div className="answer-kicker"><span>✦</span> Grounded answer</div>
              <p>
                The system uses account-level data isolation and validates every source before
                it reaches the answer pipeline. This gives each response a verifiable evidence trail.
              </p>
              <div className="citations"><span>[1] Architecture handbook · p. 8</span><span>[2] Product decisions · §4</span></div>
            </div>
          </div>
          <aside className="source-panel">
            <div className="panel-head"><span>Sources</span><b>3 cited</b></div>
            {sourceCards.map((source, index) => (
              <article className="source-card" key={source.title}>
                <span className={`file-dot ${source.tone}`}>{index + 1}</span>
                <div><strong>{source.title}</strong><small>{source.meta}</small></div>
              </article>
            ))}
            <div className="source-quote">
              <small>Selected evidence</small>
              <p>“Authorization is enforced before retrieval, not after generation.”</p>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
