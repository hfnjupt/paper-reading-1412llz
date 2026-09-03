#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const HEADERS = [
  "论文题目",
  "作者及机构",
  "摘要",
  "关键词",
  "针对的问题",
  "解决的方法",
  "创新以及借鉴地方",
  "代码位置",
  "批判地方",
];

function parseArgs(argv) {
  const args = { input: null, output: null, preview: null, python: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--input") args.input = argv[++index];
    else if (value === "--output") args.output = argv[++index];
    else if (value === "--preview") args.preview = argv[++index];
    else if (value === "--python") args.python = argv[++index];
    else if (value === "--help" || value === "-h") {
      process.stdout.write("Usage: build_coarse_workbook.mjs --input rows.json --output 论文粗读.xlsx [--preview preview.png] [--python bundled-python]\n");
      process.exit(0);
    } else throw new Error(`Unknown argument: ${value}`);
  }
  if (!args.input || !args.output) throw new Error("--input and --output are required");
  return args;
}

function cleanRows(payload) {
  const rows = Array.isArray(payload) ? payload : payload.rows;
  if (!Array.isArray(rows)) throw new Error("Input JSON must be an array or an object with a rows array");
  const richText = [];
  const values = rows.map((row, rowIndex) => HEADERS.map((header, column) => {
    const value = row?.[header];
    let text;
    if (value && typeof value === "object") {
      if (![1, 5].includes(column) || !Array.isArray(value.runs) || value.runs.length === 0) {
        throw new Error(`Row ${rowIndex + 2}, ${header}: rich text requires nonempty runs in B or F`);
      }
      const runs = value.runs.map((run) => {
        if (!run || typeof run.text !== "string" || (run.bold !== undefined && typeof run.bold !== "boolean")) {
          throw new Error(`Row ${rowIndex + 2}, ${header}: invalid rich text run`);
        }
        return { text: run.text, bold: run.bold === true };
      });
      text = runs.map((run) => run.text).join("");
      if (text.startsWith("=")) throw new Error("Rich text cannot start with '='; add a descriptive label");
      richText.push({ cell: `${String.fromCharCode(65 + column)}${rowIndex + 2}`, runs });
    } else {
      text = value === null || value === undefined ? "" : String(value);
    }
    if (header === "摘要" && !/^英文摘要：\n[\s\S]*\S[\s\S]*\n\n中文翻译：\n[\s\S]*\S[\s\S]*$/.test(text)) {
      throw new Error(`Row ${rowIndex + 2}: 摘要 requires full English then full Chinese, or explicit missing-source notices, using the documented bilingual labels`);
    }
    if (text.length > 32767) throw new Error(`Row ${rowIndex + 2}, ${header}: exceeds Excel cell limit; do not truncate the abstract`);
    return text.startsWith("=") ? `'${text}` : text;
  }));
  return { values, richText };
}

function cellHeight(value, width, abstract = false) {
  const lines = value.split(/\r?\n/).reduce((sum, line) => {
    const units = [...line].reduce((count, char) => count + (char.codePointAt(0) > 255 ? 2 : 1), 0);
    return sum + Math.max(1, Math.ceil(units / Math.max(8, width * (abstract ? 0.85 : 0.7))));
  }, 0);
  return lines * (abstract ? 18 : 22) + 8;
}

function estimatedHeight(row, widths) {
  const heights = row.map((value, index) => cellHeight(value, widths[index], index === 2));
  if (heights[2] > 400) throw new Error("Full bilingual abstract exceeds readable height at maximum column width; request layout adjustment, never shorten or truncate either language");
  if (Math.max(...heights) > 400) throw new Error("Non-abstract coarse notes exceed readable height; shorten those notes only, never the abstract");
  return Math.max(48, ...heights);
}

const args = parseArgs(process.argv.slice(2));
for (const target of [args.output, args.preview].filter(Boolean)) {
  try { await fs.access(target); } catch (error) { if (error.code === "ENOENT") continue; throw error; }
  throw new Error(`Output already exists; choose a new versioned path: ${target}`);
}
if (args.preview && path.resolve(args.preview) === path.resolve(args.output)) throw new Error("Preview and workbook must use different paths");
const payload = JSON.parse(await fs.readFile(args.input, "utf8"));
const { values: rows, richText } = cleanRows(payload);
const richTextHelper = path.join(path.dirname(fileURLToPath(import.meta.url)), "apply_rich_text.py");
if (richText.length) {
  if (!args.python) throw new Error("Rich text requires --python with the bundled Python executable");
  await fs.access(richTextHelper);
  try {
    await fs.access(`${args.output}.rich-text.json`);
    throw new Error("Rich-text sidecar already exists; choose a new output path");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}
const matrix = [HEADERS, ...(rows.length ? rows : [HEADERS.map(() => "")])];
const widths = [42, 31, 100, 29, 38, 70, 42, 41, 38];
while (widths[2] < 255 && rows.some(row => cellHeight(row[2], widths[2], true) > 380)) {
  widths[2] = Math.min(255, widths[2] + 10);
}
const rowHeights = matrix.slice(1).map(row => estimatedHeight(row, widths));
const workbook = Workbook.create();
const sheet = workbook.worksheets.add("论文粗读");
sheet.showGridLines = false;
sheet.freezePanes.freezeRows(1);
sheet.getRange(`A1:I${matrix.length}`).values = matrix;

const table = sheet.tables.add(`A1:I${matrix.length}`, true, "PaperReadingTable");
table.showFilterButton = true;
table.showBandedColumns = false;

const headerColors = ["#FFEB9C", "#00B0F0", "#00B0F0", "#FFC7CE", "#00B0F0", "#C6EFCE", "#00B0F0", "#FFEB9C", "#00B0F0"];
const headerFontColors = ["#9C6500", "#000000", "#000000", "#9C0006", "#000000", "#006100", "#000000", "#9C6500", "#000000"];
for (let column = 0; column < HEADERS.length; column += 1) {
  const cell = sheet.getCell(0, column);
  cell.format = {
    fill: headerColors[column],
    font: { bold: false, color: headerFontColors[column], size: column === 7 ? 16 : 22, name: "等线" },
    wrapText: true,
    verticalAlignment: "center",
  };
}
sheet.getRange("A1:I1").format.rowHeight = 60;

if (matrix.length > 1) {
  const body = sheet.getRange(`A2:I${matrix.length}`);
  body.format = {
    fill: "#FFFFFF",
    font: { size: 14, name: "等线", color: "#222222", bold: false },
    wrapText: true,
    verticalAlignment: "top",
    horizontalAlignment: "left",
    borders: { preset: "inside", style: "thin", color: "#E5E7EB" },
  };
  for (let row = 1; row < matrix.length; row += 1) {
    sheet.getRange(`A${row + 1}:I${row + 1}`).format.rowHeight = rowHeights[row - 1];
  }
  sheet.getRange(`C2:C${matrix.length}`).format.font.size = 12;
}

for (let column = 0; column < widths.length; column += 1) {
  sheet.getCell(0, column).format.columnWidth = widths[column];
}

const outputPath = path.resolve(args.output);
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

let richTextCheck = null;
if (richText.length) {
  const planPath = `${outputPath}.rich-text.json`;
  await fs.writeFile(planPath, JSON.stringify(richText, null, 2), { encoding: "utf8", flag: "wx" });
  const result = execFileSync(args.python, ["-X", "utf8", richTextHelper, "--workbook", outputPath, "--runs", planPath], { encoding: "utf8" });
  richTextCheck = JSON.parse(result);
}
const verifiedWorkbook = richText.length
  ? await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath))
  : workbook;
const verifiedValues = verifiedWorkbook.worksheets.getItem("论文粗读").getRange(`A1:I${matrix.length}`).values;
const normalizeEmpty = (values) => values.map((row) => row.map((value) => value ?? ""));
if (JSON.stringify(normalizeEmpty(verifiedValues)) !== JSON.stringify(normalizeEmpty(matrix))) {
  throw new Error("Export/import changed cell text; inspect the new workbook before delivery");
}

if (args.preview) {
  const previewPath = path.resolve(args.preview);
  await fs.mkdir(path.dirname(previewPath), { recursive: true });
  // The current renderer flattens rich-run fonts on import. Render the original
  // layout; the helper separately verifies the XLSX's actual per-run bold flags.
  // Never re-export verifiedWorkbook: that would flatten the rich-text styling.
  const preview = await workbook.render({
    sheetName: "论文粗读",
    range: `A1:I${Math.min(matrix.length, 12)}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
}

const check = await verifiedWorkbook.inspect({
  kind: "table",
  range: `论文粗读!A1:I${Math.min(matrix.length, 12)}`,
  tableMaxRows: 12,
  tableMaxCols: 9,
  maxChars: 6000,
});
const errors = await verifiedWorkbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 2000,
});
process.stdout.write(JSON.stringify({ output: outputPath, rows: rows.length, richTextCheck, check: check.records, formulaErrors: errors.records }, null, 2));
