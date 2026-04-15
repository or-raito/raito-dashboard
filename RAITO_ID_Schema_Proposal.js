const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, PageBreak, LevelFormat, TabStopType, TabStopPosition } = require("docx");

// ── Colors ──
const NAVY = "1B2A4A";
const ACCENT = "2E75B6";
const LIGHT_BG = "F0F4F8";
const LIGHT_ACCENT = "D5E8F0";
const WHITE = "FFFFFF";
const GRAY_BORDER = "D0D5DD";
const TEXT_DARK = "1A1A1A";
const TEXT_MED = "4A5568";
const RED = "C0392B";
const GREEN = "27AE60";
const ORANGE = "E67E22";

// ── Table helpers ──
const border = { style: BorderStyle.SINGLE, size: 1, color: GRAY_BORDER };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function headerCell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: { fill: NAVY, type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.LEFT,
      children: [new TextRun({ text, bold: true, font: "Arial", size: 18, color: WHITE })] })]
  });
}

function cell(text, width, opts = {}) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 50, bottom: 50, left: 100, right: 100 },
    children: [new Paragraph({ alignment: opts.align || AlignmentType.LEFT,
      children: [new TextRun({ text, font: "Arial", size: 17, color: opts.color || TEXT_DARK,
        bold: opts.bold || false, italics: opts.italics || false })] })]
  });
}

function codeCell(text, width, opts = {}) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 50, bottom: 50, left: 100, right: 100 },
    children: [new Paragraph({ alignment: AlignmentType.LEFT,
      children: [new TextRun({ text, font: "Courier New", size: 16, color: opts.color || TEXT_DARK })] })]
  });
}

// ── Helpers ──
function heading(text, level) {
  return new Paragraph({ heading: level, spacing: { before: level === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 },
    children: [new TextRun({ text, bold: true, font: "Arial",
      size: level === HeadingLevel.HEADING_1 ? 32 : level === HeadingLevel.HEADING_2 ? 26 : 22,
      color: NAVY })] });
}

function body(text, opts = {}) {
  return new Paragraph({ spacing: { after: opts.after || 120 },
    children: [new TextRun({ text, font: "Arial", size: 20, color: TEXT_DARK,
      bold: opts.bold || false, italics: opts.italics || false })] });
}

function bodyRuns(runs, opts = {}) {
  return new Paragraph({ spacing: { after: opts.after || 120 },
    children: runs.map(r => new TextRun({ font: "Arial", size: 20, color: TEXT_DARK, ...r })) });
}

function codeBlock(lines) {
  return lines.map(line => new Paragraph({ spacing: { after: 0 },
    indent: { left: 360 },
    children: [new TextRun({ text: line, font: "Courier New", size: 17, color: TEXT_DARK })] }));
}

function spacer(pts = 120) {
  return new Paragraph({ spacing: { after: pts }, children: [] });
}

// ── Numbering config ──
const numbering = {
  config: [
    { reference: "bullets", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "\u2013", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
    ]},
    { reference: "numbers", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    ]},
    { reference: "phases", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "Phase %1:", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 720 } } } },
    ]},
  ]
};

function bullet(text, level = 0, opts = {}) {
  return new Paragraph({ numbering: { reference: "bullets", level },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 20, color: TEXT_DARK, bold: opts.bold || false })] });
}

function bulletRuns(runs, level = 0) {
  return new Paragraph({ numbering: { reference: "bullets", level },
    spacing: { after: 80 },
    children: runs.map(r => new TextRun({ font: "Arial", size: 20, color: TEXT_DARK, ...r })) });
}

function numbered(text, opts = {}) {
  return new Paragraph({ numbering: { reference: "numbers", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 20, color: TEXT_DARK, bold: opts.bold || false })] });
}

// ── Build the document ──

const TW = 9360; // table width (US Letter, 1" margins)

const doc = new Document({
  numbering,
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: NAVY },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: NAVY },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: ACCENT },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ]
  },
  sections: [
    // ═══ COVER PAGE ═══
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children: [
        spacer(2400),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: "RAITO", font: "Arial", size: 56, bold: true, color: NAVY })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
          children: [new TextRun({ text: "ID-Based Schema Proposal", font: "Arial", size: 36, color: ACCENT })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 1 } },
          children: [new TextRun({ text: "From String Matching to Relational IDs", font: "Arial", size: 22, color: TEXT_MED, italics: true })] }),
        spacer(600),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
          children: [new TextRun({ text: "Prepared for Or Sadon", font: "Arial", size: 22, color: TEXT_MED })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
          children: [new TextRun({ text: "14 April 2026  |  Version 1.0", font: "Arial", size: 20, color: TEXT_MED })] }),
        new Paragraph({ alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Status: PROPOSAL \u2014 Pending Review", font: "Arial", size: 20, bold: true, color: ORANGE })] }),
      ]
    },

    // ═══ CONTENT ═══
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1080, left: 1440 }
        }
      },
      headers: {
        default: new Header({ children: [
          new Paragraph({ alignment: AlignmentType.RIGHT,
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: ACCENT, space: 4 } },
            children: [
              new TextRun({ text: "RAITO  ", font: "Arial", size: 16, bold: true, color: NAVY }),
              new TextRun({ text: "ID-Based Schema Proposal", font: "Arial", size: 16, color: TEXT_MED }),
            ] })
        ] })
      },
      footers: {
        default: new Footer({ children: [
          new Paragraph({ alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: "Page ", font: "Arial", size: 16, color: TEXT_MED }),
              new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: TEXT_MED }),
            ] })
        ] })
      },
      children: [

        // ═══ 1. THE PROBLEM ═══
        heading("1. The Problem: String Matching Everywhere", HeadingLevel.HEADING_1),

        body("Today, every entity in RAITO is identified by name strings. Products are Hebrew text patterns, customers are branch names that differ across distributors, and brands are sometimes a key and sometimes a display name. This creates three systemic problems:"),

        bulletRuns([
          { text: "Cross-distributor blindness: ", bold: true },
          { text: "Wolt Market appears as \u201C\u05D5\u05D5\u05DC\u05D8 \u05DE\u05E8\u05E7\u05D8\u201D from Icedream and as a different string from Biscotti. The code uses regex patterns and prefix matching to reconcile these, but new names silently fall through." },
        ]),
        bulletRuns([
          { text: "Fragile joins: ", bold: true },
          { text: "The pricing lookup tries three fallback keys (name_he, key, name_en) hoping one matches. When a customer is added in the Master Data with a slightly different spelling, the join fails silently and the portfolio shows empty cells." },
        ]),
        bulletRuns([
          { text: "Duplicated mapping logic: ", bold: true },
          { text: "config.py has CUSTOMER_NAMES_EN, CUSTOMER_PREFIXES, and extract_customer_name(). parsers.py has _MAAYAN_CHAIN_TO_PRICEDB with 8 hardcoded chains. seed_reference_data.py has CUSTOMER_ALIASES. Three separate files maintaining the same name-resolution logic." },
        ]),

        spacer(80),
        body("The SQL schema already defines proper relational tables with integer IDs (customers.id, products.id, etc.) but the runtime code completely ignores them. Parsers output dicts keyed by Hebrew strings, dashboards join on name strings, and the Master Data API stores JSONB blobs with no FK enforcement."),

        // ═══ 2. THE SOLUTION ═══
        heading("2. The Solution: ID-First Architecture", HeadingLevel.HEADING_1),

        body("Every entity gets one canonical integer ID. All data flows through IDs, never through name strings. Name strings become display attributes, not join keys."),

        spacer(40),
        bodyRuns([
          { text: "Display language rule: ", bold: true },
          { text: "All dashboard presentation uses English (name_en). Every dimension table must have a name_en column. Hebrew names (name_he) are kept for parser matching against distributor files but are never shown in the dashboard UI." },
        ]),

        spacer(60),
        heading("2.1 Dimension Tables (Already in schema.sql \u2014 Need Runtime Adoption)", HeadingLevel.HEADING_2),

        body("The good news: schema.sql already defines the right tables. The work is making the runtime code actually use them."),

        // ── brands table (NEW) ──
        heading("brands (NEW TABLE)", HeadingLevel.HEADING_3),
        body("Currently brands exist only as string keys in config.py (\"turbo\", \"danis\", \"ab\"). A proper brands table eliminates the brand_key vs brand_name confusion."),

        new Table({
          width: { size: TW, type: WidthType.DXA },
          columnWidths: [2000, 1600, 1200, 4560],
          rows: [
            new TableRow({ children: [headerCell("Column", 2000), headerCell("Type", 1600), headerCell("Nullable", 1200), headerCell("Purpose", 4560)] }),
            new TableRow({ children: [codeCell("id", 2000), cell("SERIAL PK", 1600), cell("NO", 1200), cell("The one true brand identifier", 4560)] }),
            new TableRow({ children: [codeCell("key", 2000, {fill: LIGHT_BG}), cell("VARCHAR(30)", 1600, {fill: LIGHT_BG}), cell("NO", 1200, {fill: LIGHT_BG}), cell("Slug for URLs/code: turbo, danis", 4560, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("name_en", 2000), cell("VARCHAR(100)", 1600), cell("NO", 1200), cell("Dashboard display name: Turbo, Dani\u2019s Dream Cake", 4560)] }),
            new TableRow({ children: [codeCell("name_he", 2000, {fill: LIGHT_BG}), cell("VARCHAR(100)", 1600, {fill: LIGHT_BG}), cell("YES", 1200, {fill: LIGHT_BG}), cell("Hebrew name (parser matching only, not displayed)", 4560, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("owner", 2000), cell("VARCHAR(100)", 1600), cell("YES", 1200), cell("Creator name for display", 4560)] }),
            new TableRow({ children: [codeCell("is_active", 2000, {fill: LIGHT_BG}), cell("BOOLEAN", 1600, {fill: LIGHT_BG}), cell("NO", 1200, {fill: LIGHT_BG}), cell("Default TRUE", 4560, {fill: LIGHT_BG})] }),
          ]
        }),

        spacer(60),
        bodyRuns([
          { text: "Impact: ", bold: true },
          { text: "products.brand_key becomes products.brand_id (FK). Dashboard filters reference brand_id instead of string keys. BRAND_FILTERS in config.py becomes a simple DB query." },
        ]),

        // ── products table ──
        spacer(100),
        heading("products (EXISTS \u2014 Add brand_id FK)", HeadingLevel.HEADING_3),
        body("The products table is well-designed. The key change: replace brand_key (string) with brand_id (integer FK)."),

        new Table({
          width: { size: TW, type: WidthType.DXA },
          columnWidths: [2200, 1400, 1200, 4560],
          rows: [
            new TableRow({ children: [headerCell("Column", 2200), headerCell("Type", 1400), headerCell("Status", 1200), headerCell("Notes", 4560)] }),
            new TableRow({ children: [codeCell("id", 2200), cell("SERIAL PK", 1400), cell("Exists", 1200), cell("Product ID \u2014 used in sales_transactions, inventory, pricing", 4560)] }),
            new TableRow({ children: [codeCell("sku_key", 2200, {fill: LIGHT_BG}), cell("VARCHAR(30)", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Unique slug: chocolate, vanilla, mango, pistachio, dream_cake_2", 4560, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("brand_key", 2200), cell("VARCHAR(30)", 1400), cell("REMOVE", 1200, {color: RED}), cell("Currently stores string \u201Cturbo\u201D or \u201Cdanis\u201D \u2014 replace with brand_id", 4560)] }),
            new TableRow({ children: [codeCell("brand_id", 2200, {fill: LIGHT_BG}), cell("INT FK", 1400, {fill: LIGHT_BG}), cell("NEW", 1200, {fill: LIGHT_BG, color: GREEN}), cell("References brands.id \u2014 proper relational link", 4560, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("full_name_en", 2200), cell("VARCHAR(150)", 1400), cell("Exists", 1200), cell("English display name \u2014 used in all dashboard presentation", 4560)] }),
            new TableRow({ children: [codeCell("full_name_he", 2200, {fill: LIGHT_BG}), cell("VARCHAR(150)", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Hebrew name for parser matching only (not displayed)", 4560, {fill: LIGHT_BG})] }),
          ]
        }),

        // ── customers table ──
        spacer(100),
        heading("customers (EXISTS \u2014 Already has aliases)", HeadingLevel.HEADING_3),
        body("The customers table already has name_he_aliases (TEXT[]) for Hebrew variant spellings. This is the foundation of the alias system. The key change: all runtime code must resolve raw names to customer_id via this table instead of config.py dicts."),

        new Table({
          width: { size: TW, type: WidthType.DXA },
          columnWidths: [2600, 1400, 1200, 4160],
          rows: [
            new TableRow({ children: [headerCell("Column", 2600), headerCell("Type", 1400), headerCell("Status", 1200), headerCell("Notes", 4160)] }),
            new TableRow({ children: [codeCell("id", 2600), cell("SERIAL PK", 1400), cell("Exists", 1200), cell("The canonical customer ID", 4160)] }),
            new TableRow({ children: [codeCell("name_en", 2600, {fill: LIGHT_BG}), cell("VARCHAR(100)", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Dashboard display name: Wolt Market, AMPM, Alonit", 4160, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("name_he", 2600), cell("VARCHAR(100)", 1400), cell("Exists", 1200), cell("Primary Hebrew name (parser matching)", 4160)] }),
            new TableRow({ children: [codeCell("name_he_aliases", 2600, {fill: LIGHT_BG}), cell("TEXT[]", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("All known Hebrew spelling variants for parser matching", 4160, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("primary_distributor_id", 2600), cell("INT FK", 1400), cell("Exists", 1200), cell("References distributors.id", 4160)] }),
            new TableRow({ children: [codeCell("cc_tracked", 2600, {fill: LIGHT_BG}), cell("BOOLEAN", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Whether this customer appears in CC dashboard", 4160, {fill: LIGHT_BG})] }),
          ]
        }),

        // ── sale_points table ──
        spacer(100),
        heading("sale_points (EXISTS \u2014 Key cross-distributor link)", HeadingLevel.HEADING_3),
        body("Sale points are where the cross-distributor problem is most acute. A Wolt Market branch in Tel Aviv appears under Icedream with one name and could appear under Biscotti with another. The sale_points table links (distributor_id, branch_name_he) to a canonical customer_id."),

        new Table({
          width: { size: TW, type: WidthType.DXA },
          columnWidths: [2600, 1400, 1200, 4160],
          rows: [
            new TableRow({ children: [headerCell("Column", 2600), headerCell("Type", 1400), headerCell("Status", 1200), headerCell("Notes", 4160)] }),
            new TableRow({ children: [codeCell("id", 2600), cell("SERIAL PK", 1400), cell("Exists", 1200), cell("Canonical sale point ID", 4160)] }),
            new TableRow({ children: [codeCell("customer_id", 2600, {fill: LIGHT_BG}), cell("INT FK", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Links branch to canonical customer", 4160, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("distributor_id", 2600), cell("INT FK", 1400), cell("Exists", 1200), cell("Which distributor serves this point", 4160)] }),
            new TableRow({ children: [codeCell("branch_name_he", 2600, {fill: LIGHT_BG}), cell("VARCHAR(250)", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Hebrew branch name from distributor file \u2014 displayed as-is in dashboard", 4160, {fill: LIGHT_BG})] }),
            new TableRow({ children: [codeCell("UNIQUE(dist_id, name_he)", 2600, {fill: LIGHT_BG}), cell("CONSTRAINT", 1400, {fill: LIGHT_BG}), cell("Exists", 1200, {fill: LIGHT_BG}), cell("Prevents duplicate entries per distributor", 4160, {fill: LIGHT_BG})] }),
          ]
        }),

        spacer(60),
        bodyRuns([
          { text: "Key insight: ", bold: true },
          { text: "The UNIQUE(distributor_id, branch_name_he) constraint means each branch name is unique within a distributor. When a parser encounters a branch name, it looks up (distributor_id, branch_name_he) to get the sale_point_id and customer_id in one query. No regex, no prefix matching, no fallback chains." },
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══ 2.2 NEW: Alias Resolution Table ═══
        heading("2.2 Customer Alias Resolution (NEW APPROACH)", HeadingLevel.HEADING_2),

        body("The name_he_aliases column on customers solves customer-level matching. But for the parser to resolve a raw distributor name to a customer_id efficiently, we need a flattened lookup. Two options:"),

        spacer(40),
        heading("Option A: Materialized View (Recommended)", HeadingLevel.HEADING_3),
        body("Create a view that flattens name_he_aliases into individual rows for fast lookups:"),

        ...codeBlock([
          "CREATE MATERIALIZED VIEW customer_alias_lookup AS",
          "SELECT c.id AS customer_id, c.name_en,",
          "       c.name_he AS alias",
          "FROM customers c",
          "UNION ALL",
          "SELECT c.id, c.name_en,",
          "       unnest(c.name_he_aliases) AS alias",
          "FROM customers c",
          "WHERE c.name_he_aliases IS NOT NULL;",
          "",
          "CREATE UNIQUE INDEX idx_alias_lookup ON customer_alias_lookup(alias);",
          "",
          "-- Parser resolves Hebrew \u2192 customer_id + name_en",
          "-- Dashboard always displays name_en",
        ]),

        spacer(60),
        body("Parser resolution becomes a single query:"),
        ...codeBlock([
          "SELECT customer_id FROM customer_alias_lookup",
          "WHERE alias = %s;  -- raw Hebrew name from distributor file",
        ]),

        spacer(60),
        heading("Option B: Separate alias table", HeadingLevel.HEADING_3),
        body("If aliases need per-distributor context (e.g., the same Hebrew string means different customers for different distributors), use a dedicated table:"),

        ...codeBlock([
          "CREATE TABLE customer_aliases (",
          "  id             SERIAL PRIMARY KEY,",
          "  customer_id    INT NOT NULL REFERENCES customers(id),",
          "  distributor_id INT REFERENCES distributors(id), -- NULL = all",
          "  alias_he       VARCHAR(250) NOT NULL,",
          "  UNIQUE(distributor_id, alias_he)",
          ");",
        ]),

        spacer(60),
        bodyRuns([
          { text: "Recommendation: ", bold: true },
          { text: "Start with Option A (materialized view). It uses the existing name_he_aliases column, requires zero schema changes, and covers the current use cases. Move to Option B only if a real case arises where the same Hebrew string maps to different customers depending on the distributor." },
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══ 2.3 Fact Tables ═══
        heading("2.3 Fact Tables (Already ID-Based in Schema)", HeadingLevel.HEADING_2),

        body("The good news: sales_transactions, inventory_snapshots, and price_history already use integer FKs. The problem is that the runtime code never writes to them. Instead, parsers produce in-memory dicts and dashboards consume those dicts directly."),

        spacer(60),
        heading("sales_transactions", HeadingLevel.HEADING_3),
        body("This table is fully designed and ready. Every sale row references product_id, customer_id, sale_point_id, and distributor_id as integers. The parsers just need to write here instead of returning dicts."),

        spacer(60),
        heading("price_history", HeadingLevel.HEADING_3),
        body("Uses SCD Type 2 (effective_from / effective_to dates) with proper FKs. Replaces the current approach of three fallback key lookups. A price is uniquely identified by (product_id, customer_id, effective_from)."),

        spacer(60),
        heading("inventory_snapshots", HeadingLevel.HEADING_3),
        body("Already references distributor_id and product_id. Point-in-time snapshots with a UNIQUE constraint on (distributor_id, product_id, snapshot_date)."),

        spacer(60),
        heading("weekly_chart_overrides", HeadingLevel.HEADING_3),
        bodyRuns([
          { text: "Current: ", bold: true },
          { text: "Uses distributor as a TEXT string. " },
          { text: "Proposed: ", bold: true },
          { text: "Change to distributor_id INT FK. This is a small change but eliminates one more string join." },
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══ 3. MIGRATION PATH ═══
        heading("3. Migration Path", HeadingLevel.HEADING_1),

        body("This is a large change but can be done incrementally. Each phase delivers standalone value and can be deployed independently."),

        spacer(80),

        // Phase 1
        heading("Phase 1: Activate the Alias Lookup", HeadingLevel.HEADING_2),
        bodyRuns([
          { text: "Goal: ", bold: true },
          { text: "Parsers resolve raw Hebrew names to customer_id and product_id at parse time, instead of passing strings through the pipeline." },
        ]),

        bullet("Create the customer_alias_lookup materialized view from existing name_he_aliases data"),
        bullet("Add a database_manager.py module with resolve_customer(raw_name, distributor_id) and resolve_product(hebrew_text) functions"),
        bullet("These functions query the DB once at startup, cache the result, and return integer IDs"),
        bullet("Parsers call these resolvers instead of doing regex/prefix matching inline"),
        bullet("Unknown names get logged with the raw string and distributor, flagged for manual mapping"),

        spacer(40),
        bodyRuns([
          { text: "What changes: ", bold: true },
          { text: "parsers.py, config.py (extract_customer_name removed), database_manager.py (new). Dashboards unchanged \u2014 they still consume the same dict structure, but with IDs attached." },
        ]),
        bodyRuns([
          { text: "Risk: ", bold: true },
          { text: "Low. Parser output gains ID fields but existing string fields are preserved. Dashboards ignore the new fields until Phase 3." },
        ]),

        spacer(120),

        // Phase 2
        heading("Phase 2: Parsers Write to sales_transactions", HeadingLevel.HEADING_2),
        bodyRuns([
          { text: "Goal: ", bold: true },
          { text: "Every parsed sale row gets inserted into sales_transactions with proper FKs. The DB becomes the source of truth for historical data." },
        ]),

        bullet("After resolving IDs (Phase 1), parsers INSERT each row into sales_transactions"),
        bullet("ingestion_batches tracks which files have been processed (prevents double-import)"),
        bullet("The upload endpoint writes to DB, then invalidates the dashboard cache"),
        bullet("Weekly chart data comes from DB queries instead of hardcoded Python arrays"),

        spacer(40),
        bodyRuns([
          { text: "What changes: ", bold: true },
          { text: "parsers.py (adds DB writes), db_dashboard.py (reads from sales_transactions instead of re-parsing), cc_dashboard_v2.py (weekly arrays from DB)." },
        ]),
        bodyRuns([
          { text: "Impact: ", bold: true },
          { text: "This eliminates CC audit issues #1 and #2 (hardcoded weekly data, no DB sync). Also fixes the dual code path problem (audit #9) because both local and Cloud Run read from the same DB." },
        ]),

        spacer(120),

        // Phase 3
        heading("Phase 3: Dashboards Query by ID", HeadingLevel.HEADING_2),
        bodyRuns([
          { text: "Goal: ", bold: true },
          { text: "Dashboard tabs read from the database using ID-based queries instead of consuming parser dicts." },
        ]),

        bullet("BO tab: SQL query groups by product_id, distributor_id, month \u2014 joins to products/brands for display names"),
        bullet("CC tab: SQL query groups by customer_id, product_id, month \u2014 joins to customers for display"),
        bullet("SP tab: SQL query groups by sale_point_id, month \u2014 joins to sale_points and customers"),
        bullet("GEO tab: Already uses DB for geocoding \u2014 extend to pull sale data by sale_point_id"),

        spacer(40),
        bodyRuns([
          { text: "What changes: ", bold: true },
          { text: "All dashboard generators switch from dict-walking to SQL queries. The Python dict structure becomes an intermediate cache, not the primary data source." },
        ]),
        bodyRuns([
          { text: "Impact: ", bold: true },
          { text: "Eliminates the need for parsers.consolidate_data() at render time. Dashboard renders from DB, not from re-parsing Excel files on every request." },
        ]),

        spacer(120),

        // Phase 4
        heading("Phase 4: Master Data API Uses FKs", HeadingLevel.HEADING_2),
        bodyRuns([
          { text: "Goal: ", bold: true },
          { text: "The Master Data tab CRUD operations validate foreign keys and maintain referential integrity." },
        ]),

        bullet("Replace JSONB master_data table with proper relational tables (already exist in schema.sql)"),
        bullet("API endpoints validate FKs: creating a pricing row requires valid product_id and customer_id"),
        bullet("Portfolio matrix becomes a SQL JOIN, not a Python dict-merge with three fallback keys"),
        bullet("Export/import round-trips preserve IDs, not just display names"),

        spacer(40),
        bodyRuns([
          { text: "Impact: ", bold: true },
          { text: "Eliminates audit issues: Master Data #2 (export/import round-trip), #3 (pricing key mismatch), #4 (empty PKs), #5 (JSONB no schema)." },
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══ 4. ENTITY RELATIONSHIP DIAGRAM ═══
        heading("4. Entity Relationships", HeadingLevel.HEADING_1),
        body("The complete relationship map showing how IDs flow through the system:"),

        spacer(60),
        ...codeBlock([
          "brands",
          "  \u2502",
          "  \u251C\u2500\u2500 products.brand_id \u2500\u2500\u2510",
          "  \u2502                        \u251C\u2500\u2500 sales_transactions.product_id",
          "  \u2502                        \u251C\u2500\u2500 price_history.product_id",
          "  \u2502                        \u2514\u2500\u2500 inventory_snapshots.product_id",
          "  \u2502",
          "distributors",
          "  \u2502",
          "  \u251C\u2500\u2500 customers.primary_distributor_id",
          "  \u251C\u2500\u2500 sale_points.distributor_id",
          "  \u251C\u2500\u2500 sales_transactions.distributor_id",
          "  \u251C\u2500\u2500 price_history.distributor_id",
          "  \u251C\u2500\u2500 inventory_snapshots.distributor_id",
          "  \u2514\u2500\u2500 ingestion_batches.distributor_id",
          "  \u2502",
          "customers",
          "  \u2502",
          "  \u251C\u2500\u2500 sale_points.customer_id",
          "  \u251C\u2500\u2500 sales_transactions.customer_id",
          "  \u2514\u2500\u2500 price_history.customer_id",
          "  \u2502",
          "  \u2514\u2500\u2500 customer_alias_lookup (materialized view)",
          "       Maps: raw Hebrew name \u2192 customer_id",
          "  \u2502",
          "sale_points",
          "  \u2502",
          "  \u2514\u2500\u2500 sales_transactions.sale_point_id",
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══ 5. WHAT THIS FIXES ═══
        heading("5. Audit Issues Resolved by This Migration", HeadingLevel.HEADING_1),

        body("Cross-referencing against the 14 open audit issues:"),
        spacer(60),

        new Table({
          width: { size: TW, type: WidthType.DXA },
          columnWidths: [600, 2000, 4160, 1200, 1400],
          rows: [
            new TableRow({ children: [
              headerCell("#", 600), headerCell("Issue", 2000), headerCell("How IDs Fix It", 4160),
              headerCell("Phase", 1200), headerCell("Severity", 1400)
            ]}),
            new TableRow({ children: [
              cell("1", 600), cell("CC weekly data hardcoded", 2000),
              cell("Weekly data from sales_transactions DB query, not Python arrays", 4160),
              cell("Phase 2", 1200), cell("CRITICAL", 1400, {color: RED, bold: true})
            ]}),
            new TableRow({ children: [
              cell("2", 600, {fill: LIGHT_BG}), cell("CC no DB sync", 2000, {fill: LIGHT_BG}),
              cell("CC reads from DB via ID-based queries", 4160, {fill: LIGHT_BG}),
              cell("Phase 2-3", 1200, {fill: LIGHT_BG}), cell("MEDIUM", 1400, {fill: LIGHT_BG, color: ORANGE})
            ]}),
            new TableRow({ children: [
              cell("3", 600), cell("MD export/import round-trip", 2000),
              cell("IDs preserved across export/import; FKs validated on import", 4160),
              cell("Phase 4", 1200), cell("CRITICAL", 1400, {color: RED, bold: true})
            ]}),
            new TableRow({ children: [
              cell("4", 600, {fill: LIGHT_BG}), cell("MD pricing key mismatch", 2000, {fill: LIGHT_BG}),
              cell("price_history uses product_id + customer_id FKs. No fallback chains.", 4160, {fill: LIGHT_BG}),
              cell("Phase 4", 1200, {fill: LIGHT_BG}), cell("MEDIUM", 1400, {fill: LIGHT_BG, color: ORANGE})
            ]}),
            new TableRow({ children: [
              cell("5", 600), cell("MD no FK validation", 2000),
              cell("API validates all FKs before insert/update", 4160),
              cell("Phase 4", 1200), cell("MEDIUM", 1400, {color: ORANGE})
            ]}),
            new TableRow({ children: [
              cell("6", 600, {fill: LIGHT_BG}), cell("MD JSONB no schema", 2000, {fill: LIGHT_BG}),
              cell("Replace JSONB with proper relational tables", 4160, {fill: LIGHT_BG}),
              cell("Phase 4", 1200, {fill: LIGHT_BG}), cell("MEDIUM", 1400, {fill: LIGHT_BG, color: ORANGE})
            ]}),
            new TableRow({ children: [
              cell("9", 600), cell("Dual code paths", 2000),
              cell("Single DB as SSOT. Both local and Cloud Run query same tables.", 4160),
              cell("Phase 2-3", 1200), cell("CRITICAL", 1400, {color: RED, bold: true})
            ]}),
            new TableRow({ children: [
              cell("10", 600, {fill: LIGHT_BG}), cell("Ma\u2019ayan only 8 chains", 2000, {fill: LIGHT_BG}),
              cell("customer_alias_lookup covers all aliases. New chains flagged automatically.", 4160, {fill: LIGHT_BG}),
              cell("Phase 1", 1200, {fill: LIGHT_BG}), cell("MEDIUM", 1400, {fill: LIGHT_BG, color: ORANGE})
            ]}),
            new TableRow({ children: [
              cell("12", 600), cell("Parsers fail silently", 2000),
              cell("Unknown names logged with raw string + distributor for review", 4160),
              cell("Phase 1", 1200), cell("MEDIUM", 1400, {color: ORANGE})
            ]}),
          ]
        }),

        spacer(60),
        bodyRuns([
          { text: "Score: ", bold: true },
          { text: "This migration resolves 9 of 14 open audit issues, including 3 of 4 remaining CRITICALs. The remaining 5 issues (GEO API key, SP filter behavior, SP branch matching, Biscotti filename, BO upload flow) are independent and can be fixed in parallel." },
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══ 6. IMPLEMENTATION SEQUENCE ═══
        heading("6. Recommended Implementation Sequence", HeadingLevel.HEADING_1),

        body("Estimated effort per phase, assuming we work on this together:"),

        spacer(60),
        new Table({
          width: { size: TW, type: WidthType.DXA },
          columnWidths: [1800, 2400, 2000, 1600, 1560],
          rows: [
            new TableRow({ children: [
              headerCell("Phase", 1800), headerCell("Scope", 2400), headerCell("Files Changed", 2000),
              headerCell("Effort", 1600), headerCell("Deploys", 1560)
            ]}),
            new TableRow({ children: [
              cell("1. Alias Lookup", 1800, {bold: true}), cell("Resolver functions + materialized view", 2400),
              cell("database_manager.py, parsers.py, config.py", 2000), cell("1 session", 1600), cell("DB + code", 1560)
            ]}),
            new TableRow({ children: [
              cell("2. DB Writes", 1800, {bold: true, fill: LIGHT_BG}), cell("Parsers INSERT to sales_transactions", 2400, {fill: LIGHT_BG}),
              cell("parsers.py, db_dashboard.py", 2000, {fill: LIGHT_BG}), cell("2 sessions", 1600, {fill: LIGHT_BG}), cell("DB + code", 1560, {fill: LIGHT_BG})
            ]}),
            new TableRow({ children: [
              cell("3. Dashboard SQL", 1800, {bold: true}), cell("Tabs read from DB, not dicts", 2400),
              cell("All dashboard .py files", 2000), cell("2-3 sessions", 1600), cell("Code only", 1560)
            ]}),
            new TableRow({ children: [
              cell("4. MD Relational", 1800, {bold: true, fill: LIGHT_BG}), cell("JSONB \u2192 proper tables + FK validation", 2400, {fill: LIGHT_BG}),
              cell("db_dashboard.py, master_data_parser.py", 2000, {fill: LIGHT_BG}), cell("1-2 sessions", 1600, {fill: LIGHT_BG}), cell("DB + code", 1560, {fill: LIGHT_BG})
            ]}),
          ]
        }),

        spacer(120),

        heading("6.1 Quick Win: Phase 1 Starter", HeadingLevel.HEADING_2),
        body("Phase 1 can be started immediately with minimal risk. Here\u2019s the concrete first step:"),

        numbered("Run the materialized view SQL on the production database"),
        numbered("Create database_manager.py with resolve_customer() and resolve_product() functions"),
        numbered("Add a \u201Cdry run\u201D mode to parsers.py that resolves names and reports unmatched entries"),
        numbered("Review unmatched entries and add missing aliases to customers.name_he_aliases"),
        numbered("Switch parsers to use resolvers, preserving backward compatibility by keeping string keys alongside IDs"),

        spacer(120),
        body("This document is a living reference. Once you approve the approach, we can start Phase 1 in the next session.", { italics: true }),

      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/focused-brave-albattani/mnt/dataset/RAITO_ID_Schema_Proposal.docx", buffer);
  console.log("Document created successfully");
});
