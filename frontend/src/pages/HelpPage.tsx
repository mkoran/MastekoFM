import { Link } from 'react-router-dom'

/**
 * Sprint G2: in-app manual at /help. Plain JSX (no markdown dep) so it
 * stays in version control with the codebase. Update freely as the system
 * evolves — this is the canonical user-facing reference.
 */

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mb-8 scroll-mt-4">
      <h2 className="mb-3 border-b border-gray-200 pb-1 text-xl font-semibold text-gray-900">{title}</h2>
      <div className="space-y-3 text-sm text-gray-700">{children}</div>
    </section>
  )
}

function Code({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-800">{children}</code>
}

function Tag({ color, children }: { color: 'yellow' | 'blue' | 'green' | 'red' | 'gray'; children: React.ReactNode }) {
  const cls = {
    yellow: 'bg-yellow-100 text-yellow-800',
    blue: 'bg-blue-100 text-blue-800',
    green: 'bg-green-100 text-green-800',
    red: 'bg-red-100 text-red-800',
    gray: 'bg-gray-100 text-gray-700',
  }[color]
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{children}</span>
}

export default function HelpPage() {
  return (
    <div className="mx-auto flex max-w-6xl gap-8 p-6">
      {/* Table of contents */}
      <aside className="sticky top-4 hidden h-[calc(100vh-2rem)] w-56 flex-shrink-0 overflow-y-auto text-sm lg:block">
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-gray-500">Manual</h3>
        <ul className="space-y-1.5">
          {[
            ['quickstart', 'Quickstart'],
            ['core-concepts', 'Core concepts'],
            ['three-way', 'Three-way composition'],
            ['workspaces', 'Workspaces'],
            ['models', 'Models'],
            ['packs', 'AssumptionPacks (inputs)'],
            ['templates', 'OutputTemplates'],
            ['runs', 'Running calculations'],
            ['drive-layout', 'Drive folder layout'],
            ['versioning', 'Filename versioning'],
            ['tab-prefix', 'Tab prefix contract'],
            ['troubleshooting', 'Troubleshooting'],
            ['glossary', 'Glossary'],
          ].map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} className="block py-0.5 text-gray-600 hover:text-blue-600">
                {label}
              </a>
            </li>
          ))}
        </ul>
      </aside>

      <article className="flex-1">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">MastekoFM — User manual</h1>
          <p className="mt-2 text-sm text-gray-600">
            How to use MastekoFM end-to-end. Short and practical. Last updated alongside Sprint G2.
          </p>
        </header>

        <Section id="quickstart" title="Quickstart">
          <p>The fastest path to seeing the system work end-to-end:</p>
          <ol className="ml-5 list-decimal space-y-2">
            <li>
              <strong>Sign in with Google</strong> — top of the <Link to="/settings" className="text-blue-600 hover:underline">Settings</Link>{' '}
              page. Required so the system can read/write files in your Drive.
            </li>
            <li>
              <strong>Set the Drive root folder</strong> — also on Settings. Paste the URL or ID of any Drive folder you own.
              All MastekoFM files (Models, AssumptionPacks, OutputTemplates, Run outputs) live under this folder.
            </li>
            <li>
              <strong>Click <Tag color="green">🌱 Seed Hello World</Tag></strong> on the Settings page. Creates a tiny demo
              Project (a + b math) so you can see all the moving parts.
            </li>
            <li>
              <strong>Open the Hello World project</strong> from the success banner. Click <Tag color="green">+ New Run</Tag>,
              pick the three pieces, hit ▶ Run. Watch the run polling indicator. ~10–90s later you have an output.
            </li>
          </ol>
        </Section>

        <Section id="core-concepts" title="Core concepts">
          <p>MastekoFM treats financial modelling as composition of three independently-versioned things:</p>
          <ul className="ml-5 list-disc space-y-2">
            <li>
              <Tag color="blue">Model</Tag> — the calculation engine (a .xlsx with input tabs, calc tabs, and output tabs). Model
              authors update this when the math changes.
            </li>
            <li>
              <Tag color="yellow">AssumptionPack</Tag> — the numbers (a .xlsx containing only the input tabs). Analysts edit packs to
              try different scenarios. One Project can have many packs.
            </li>
            <li>
              <Tag color="green">OutputTemplate</Tag> — the report shape (a .xlsx with placeholders for Model outputs). Designers
              update this when the report layout changes.
            </li>
          </ul>
          <p>
            A <strong>Run</strong> picks one of each and produces an output artifact. Every Run is immutable: it pins the exact
            versions of all three pieces it used, so you can always reproduce the calculation.
          </p>
        </Section>

        <Section id="three-way" title="Three-way composition">
          <p>The composition is explicit at runtime — you choose the three pieces in the New Run modal:</p>
          <pre className="overflow-x-auto rounded bg-gray-900 p-3 text-xs text-gray-100">
{`AssumptionPack vN  ──┐
Model vM           ──┼─→  Run  →  output_v001.xlsx
OutputTemplate vO  ──┘                output_v001.pdf  (future)
                                       output_v001.docx (future)`}
          </pre>
          <p>
            The system <strong>validates compatibility</strong> before letting you run: every <Code>I_*</Code> tab declared on the
            Model must exist on the AssumptionPack, and every <Code>M_*</Code> tab on the OutputTemplate must have a matching{' '}
            <Code>O_*</Code> tab on the Model. The New Run modal shows live ✓/✗ feedback as you pick each piece.
          </p>
          <p>
            Execution is <strong>two-stage</strong>:
          </p>
          <ol className="ml-5 list-decimal">
            <li>Stage 1 — Pack inputs overlay onto Model inputs; LibreOffice recalculates; Model outputs are extracted.</li>
            <li>Stage 2 — Model outputs inject into OutputTemplate <Code>M_*</Code> tabs; LibreOffice recalculates; final artifact saved to Drive.</li>
          </ol>
        </Section>

        <Section id="workspaces" title="Workspaces">
          <p>
            A <strong>Workspace</strong> is the top-level container. It holds Models, OutputTemplates, and Projects. A Workspace
            is assigned to people via membership.
          </p>
          <p>On first sign-in you get a <Code>Personal</Code> workspace. You can:</p>
          <ul className="ml-5 list-disc space-y-1">
            <li>Click the workspace name in the sidebar (top-left) to open <strong>Workspace settings</strong>.</li>
            <li>Edit name, description, members, archive/unarchive.</li>
            <li>Open the workspace's Drive folder via 📁.</li>
          </ul>
          <p className="text-xs text-amber-700">
            Note: <strong>permissions are not enforced yet</strong>. Members are tracked but every signed-in user can read/write
            every workspace. Role-based access control comes in a future sprint.
          </p>
        </Section>

        <Section id="models" title="Models">
          <p>A Model is a .xlsx file with three kinds of tabs (case-sensitive prefix):</p>
          <ul className="ml-5 list-disc space-y-1">
            <li><Tag color="yellow">I_*</Tag> — input tabs (filled by AssumptionPacks at run time)</li>
            <li>(no prefix) — calc tabs (formulas only; never edited by users)</li>
            <li><Tag color="green">O_*</Tag> — output tabs (computed; never edited)</li>
          </ul>
          <p>
            On the <Link to="/models" className="text-blue-600 hover:underline">Models page</Link> you'll see one row per Model
            with: name, code, version, tab counts, Drive folder link, "Open in Sheets" (latest version), and a 📊 Calculations
            link that filters /runs by this Model.
          </p>
          <p>
            Click a Model name to open its <strong>detail page</strong>: hero with Drive folder URL · I_/calc/O_ tab structure ·
            full version history (every <Code>{'{code}_v001.xlsx'}</Code>, <Code>_v002.xlsx</Code>, ... visible with timestamps and
            direct open/download) · Calculations (Runs that used this Model).
          </p>
          <p>
            <strong>Uploading a new version</strong> creates a new file in the Model's Drive folder named{' '}
            <Code>{'{code}_v(N+1).xlsx'}</Code>. Older versions stay accessible — that's your version history.
          </p>
        </Section>

        <Section id="packs" title="AssumptionPacks (the inputs)">
          <p>
            An AssumptionPack is a .xlsx containing <strong>only</strong> <Code>I_*</Code> tabs — the same input tabs declared on the Project's
            default Model. Each Project can have many packs (e.g. base case, optimistic, pessimistic).
          </p>
          <p>To create a pack, open a project and use the <strong>New AssumptionPack</strong> form on the left:</p>
          <ul className="ml-5 list-disc space-y-1">
            <li><strong>Seed from default Model</strong> — copies just the I_ tabs from the Model and fills with defaults</li>
            <li><strong>Clone from existing pack</strong> — copies another pack as starting point</li>
          </ul>
          <p>
            <strong>Editing inputs</strong>: click <Tag color="green">Edit in Google Sheets →</Tag> on the pack's detail panel.
            Drive opens it in Sheets in Office mode (file stays as .xlsx). Save in Sheets — the file is updated in place.
          </p>
          <p>
            <strong>Re-uploading</strong>: use the file picker to upload a new .xlsx version. This creates a NEW versioned file
            in the pack's Drive folder ({'{pack_code}_v002.xlsx'}, etc) — your old version is preserved.
          </p>
          <p>
            <strong>Version history</strong>: click <Tag color="gray">📜 Version history</Tag> on the pack detail panel to see
            every uploaded version with timestamps + direct open/download.
          </p>
        </Section>

        <Section id="templates" title="OutputTemplates (the report shape)">
          <p>
            An OutputTemplate is what shapes the Run's final artifact. For format=<Code>xlsx</Code> (only one supported today;
            PDF + Word coming soon), it's a .xlsx with:
          </p>
          <ul className="ml-5 list-disc space-y-1">
            <li><Tag color="blue">M_*</Tag> — placeholder tabs filled by the Model's <Code>O_*</Code> tab values</li>
            <li>(no prefix) — calc tabs that combine M_ values into the final report</li>
            <li><Tag color="green">O_*</Tag> — the user-facing artifact tabs</li>
          </ul>
          <p>Upload from the <Link to="/output-templates" className="text-blue-600 hover:underline">Output Templates page</Link>.</p>
        </Section>

        <Section id="runs" title="Running calculations">
          <p>From any Project page, click <Tag color="green">+ New Run</Tag>:</p>
          <ol className="ml-5 list-decimal space-y-1">
            <li>Pick an AssumptionPack (the numbers)</li>
            <li>Pick a Model (the engine)</li>
            <li>Pick an OutputTemplate (the report shape)</li>
            <li>The system shows ✅ Compatible / ❌ Not compatible based on tab contracts</li>
            <li>Hit ▶ Run</li>
          </ol>
          <p>
            POST /api/runs returns 202 Accepted in &lt;100ms — the actual compute happens async via Cloud Tasks. You're redirected
            to the Run detail page where a polling indicator shows pending → running → completed (typically 10–90s for Hello World;
            longer for big models).
          </p>
          <p>
            <strong>Run detail page</strong>: composition summary (clickable names) · 📁 Drive folder URL · artifacts table
            (xlsx today; pdf/docx future) · warnings · retry button (creates a new Run with same composition).
          </p>
          <p>
            <strong>Listing all runs</strong>: <Link to="/runs" className="text-blue-600 hover:underline">/runs</Link> filters by
            project, user (email), or status. Runs are sorted newest first.
          </p>
        </Section>

        <Section id="drive-layout" title="Drive folder layout">
          <p>Everything MastekoFM creates lives under your configured Drive root folder, in this structure:</p>
          <pre className="overflow-x-auto rounded bg-gray-900 p-3 text-[11px] leading-relaxed text-gray-100">
{`{drive_root}/
└── MastekoFM/
    └── Workspaces/
        └── {workspace_code}/
            ├── Models/
            │   └── {model_code}/
            │       ├── {model_code}_v001.xlsx
            │       ├── {model_code}_v002.xlsx
            │       └── ...
            ├── OutputTemplates/
            │   └── {tpl_code}/
            │       └── {tpl_code}_v001.xlsx
            └── Projects/
                └── {project_code}/
                    ├── AssumptionPacks/
                    │   └── {pack_code}/
                    │       ├── {pack_code}_v001.xlsx
                    │       ├── {pack_code}_v002.xlsx
                    │       └── ...
                    └── Runs/
                        └── 20260427-180000_{pack}_{tpl}/   ← per-Run folder
                            ├── {pack}_{tpl}_v001.xlsx
                            ├── {pack}_{tpl}_v001.pdf       (future)
                            └── run-log_v001.txt`}
          </pre>
          <p>
            <strong>Each entity has its own folder.</strong> Each Run gets a timestamped folder so all artifacts (xlsx today, PDF
            and Word coming) live alongside.
          </p>
        </Section>

        <Section id="versioning" title="Filename versioning">
          <p>Every artifact filename includes its version, encoded as:</p>
          <pre className="rounded bg-gray-100 p-3 text-xs">{'{entity_code}_v{NNN}.{ext}'}</pre>
          <ul className="ml-5 list-disc space-y-1">
            <li><Code>NNN</Code> is zero-padded (3 digits) so lexical sort = version sort = chronological sort.</li>
            <li>Examples: <Code>helloworld_inputs_v001.xlsx</Code>, <Code>campus_adele_model_v027.xlsx</Code>.</li>
            <li>Each upload creates a NEW file with a bumped version number. Old versions stay in the folder — that's your audit trail.</li>
            <li>The "current" version is the one with the highest number; the system tracks it via a <Code>drive_file_id</Code> field that always points at the latest.</li>
          </ul>
        </Section>

        <Section id="tab-prefix" title="Tab prefix contract">
          <p>Tab prefixes are case-sensitive and define what each tab is for:</p>
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-2 py-1 text-left">Prefix</th>
                <th className="px-2 py-1 text-left">Meaning</th>
                <th className="px-2 py-1 text-left">Where used</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t">
                <td className="px-2 py-1"><Code>I_*</Code></td>
                <td className="px-2 py-1">Input tab — filled by an AssumptionPack at run time</td>
                <td className="px-2 py-1">Model, AssumptionPack</td>
              </tr>
              <tr className="border-t">
                <td className="px-2 py-1"><Code>O_*</Code></td>
                <td className="px-2 py-1">Output tab — published by a Model</td>
                <td className="px-2 py-1">Model</td>
              </tr>
              <tr className="border-t">
                <td className="px-2 py-1"><Code>M_*</Code></td>
                <td className="px-2 py-1">Model-output tab — filled by Model's <Code>O_*</Code> values</td>
                <td className="px-2 py-1">OutputTemplate only</td>
              </tr>
              <tr className="border-t">
                <td className="px-2 py-1">(other)</td>
                <td className="px-2 py-1">Calculation tab — formulas only, never user-edited</td>
                <td className="px-2 py-1">Model, OutputTemplate</td>
              </tr>
            </tbody>
          </table>
          <p className="text-amber-700">
            Strict case sensitivity: <Code>i_Cap Table</Code> is a calc tab, NOT an input. Validators use literal{' '}
            <Code>str.startswith(&quot;I_&quot;)</Code>.
          </p>
        </Section>

        <Section id="troubleshooting" title="Troubleshooting">
          <ul className="ml-5 list-disc space-y-3">
            <li>
              <strong>Run failed: "Drive download failed for ..."</strong> — typically means you're signed in with a Google account
              that doesn't own the file. The narrow OAuth scope (<Code>drive.file</Code>) only sees files THIS app uploaded under
              the currently signed-in account. Sign in with the account that originally uploaded the file. (The system also
              auto-falls-back to a service-account read; if that also fails, you'll see a clear message in the run detail page.)
            </li>
            <li>
              <strong>"Drive token expired"</strong> — Google OAuth tokens last ~1 hour. Click <strong>Refresh Google sign-in</strong> on the
              Settings page to mint a fresh one.
            </li>
            <li>
              <strong>Sidebar shows no workspace</strong> — your first sign-in auto-creates a "Personal" workspace via{' '}
              <Code>GET /api/workspaces/me/default</Code>. If it doesn't appear, check Settings → Google sign-in is active.
            </li>
            <li>
              <strong>I don't see my project</strong> — check that you're in the right workspace (top-left in sidebar). Projects
              are workspace-scoped. The Projects list currently shows ALL projects (no workspace filter applied), so if you have
              two workspaces you'll see both.
            </li>
            <li>
              <strong>Run hangs in "running" forever</strong> — the engine has a 120s LibreOffice timeout per stage. If the model
              is very large or the container is cold-starting, this can hit. Check the Run detail page for a clear error message,
              or look at Cloud Run logs.
            </li>
          </ul>
        </Section>

        <Section id="glossary" title="Glossary">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-[max-content_1fr]">
            <dt className="font-semibold text-gray-900">Workspace</dt>
            <dd>Top-level container. Holds Models, OutputTemplates, and Projects. Has a member list.</dd>

            <dt className="font-semibold text-gray-900">Project</dt>
            <dd>Organizational scope inside a Workspace. Holds AssumptionPacks. Has an optional default Model.</dd>

            <dt className="font-semibold text-gray-900">Model</dt>
            <dd>Versioned .xlsx with I_/O_/calc tabs. The "calculation engine".</dd>

            <dt className="font-semibold text-gray-900">AssumptionPack</dt>
            <dd>Versioned .xlsx with only I_ tabs. Belongs to a Project. The "numbers".</dd>

            <dt className="font-semibold text-gray-900">OutputTemplate</dt>
            <dd>Versioned .xlsx with M_/calc/O_ tabs. The "report shape".</dd>

            <dt className="font-semibold text-gray-900">Run</dt>
            <dd>An immutable record of one (Model × Pack × OutputTemplate) execution + its output artifacts.</dd>

            <dt className="font-semibold text-gray-900">Three-way composition</dt>
            <dd>The pattern: Run = Model + AssumptionPack + OutputTemplate. Each varies independently.</dd>

            <dt className="font-semibold text-gray-900">Versioned filename</dt>
            <dd>The naming convention: <Code>{'{code}_v{NNN}.{ext}'}</Code>. Sorts lexically = chronologically.</dd>
          </dl>
        </Section>

        <footer className="mt-12 border-t pt-4 text-xs text-gray-500">
          <p>
            Found a gap or error in this manual? It lives at <Code>frontend/src/pages/HelpPage.tsx</Code>. Edit and ship.
          </p>
        </footer>
      </article>
    </div>
  )
}
