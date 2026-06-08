import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const payloadPath = process.argv[2];
if (!payloadPath) {
  throw new Error("Missing payload path.");
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));

const COLUMNS = payload.columns;
const HEADERS = {
  platform: "平台名",
  title: "商品标题",
  shop_name: "店铺名",
  sales_display: "平台展示销量",
  sales_num: "销量下限",
  price: "价格",
  location: "发货地/商家地址",
  product_url: "商品链接",
  is_chenghai: "是否澄海/汕头",
  data_note: "数据说明",
};

function rowsToMatrix(rows, includeRank = true) {
  const headers = includeRank ? ["排名", ...COLUMNS.map((key) => HEADERS[key])] : COLUMNS.map((key) => HEADERS[key]);
  const matrixRows = rows.map((row, index) => {
    const values = COLUMNS.map((key) => row[key] ?? "");
    return includeRank ? [index + 1, ...values] : values;
  });
  return [headers, ...matrixRows];
}

function sanitizeSheetName(name) {
  const cleaned = String(name || "平台")
    .replace(/[\\/*?:[\]]/g, " ")
    .trim()
    .slice(0, 31);
  return cleaned || "平台";
}

function columnLetter(index) {
  let letter = "";
  let n = index + 1;
  while (n > 0) {
    const mod = (n - 1) % 26;
    letter = String.fromCharCode(65 + mod) + letter;
    n = Math.floor((n - mod) / 26);
  }
  return letter;
}

function applyTableStyle(sheet, rowCount, colCount, tableName) {
  if (rowCount < 1 || colCount < 1) {
    return;
  }
  const endCell = `${columnLetter(colCount - 1)}${rowCount}`;
  const range = sheet.getRange(`A1:${endCell}`);
  range.format.borders = { preset: "all", style: "thin", color: "#D9E2EC" };
  sheet.getRange(`A1:${columnLetter(colCount - 1)}1`).format = {
    fill: "#134E4A",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:${endCell}`).format = {
      wrapText: true,
      verticalAlignment: "top",
    };
  }
  sheet.freezePanes.freezeRows(1);
  const table = sheet.tables.add(`A1:${endCell}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;

  const widths = [54, 80, 300, 170, 110, 94, 90, 150, 280, 120, 220];
  widths.slice(0, colCount).forEach((width, index) => {
    sheet.getRange(`${columnLetter(index)}:${columnLetter(index)}`).format.columnWidthPx = width;
  });
  sheet.getRange(`A:A`).format.horizontalAlignment = "center";
  sheet.getRange(`F:F`).format.numberFormat = "#,##0";
}

async function exportWorkbook(workbook, outputPath) {
  const file = await SpreadsheetFile.exportXlsx(workbook);
  await fs.mkdir(outputPath.replace(/[\\/][^\\/]+$/, ""), { recursive: true });
  await file.save(outputPath);
}

async function buildTopByPlatform() {
  const workbook = Workbook.create();
  const entries = Object.entries(payload.platform_top);

  if (entries.length === 0) {
    const sheet = workbook.worksheets.add("无澄海记录");
    sheet.getRange("A1").values = [["未找到发货地/商家地址含“澄海”或“汕头”的记录"]];
    sheet.getRange("A1").format = { font: { bold: true } };
  } else {
    entries.forEach(([platform, rows], sheetIndex) => {
      const sheet = workbook.worksheets.add(sanitizeSheetName(platform));
      const matrix = rowsToMatrix(rows, true);
      sheet.getRangeByIndexes(0, 0, matrix.length, matrix[0].length).values = matrix;
      applyTableStyle(sheet, matrix.length, matrix[0].length, `PlatformTop${sheetIndex + 1}`);
    });
  }

  const renderedSheets = workbook.worksheets.items.map((sheet) => sheet.name);
  for (const sheetName of renderedSheets) {
    await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  }
  await exportWorkbook(workbook, payload.outputs.top_by_platform);
}

async function buildOverallTop20() {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("跨平台Top20");
  const matrix = rowsToMatrix(payload.overall_top20, true);
  sheet.getRangeByIndexes(0, 0, matrix.length, matrix[0].length).values = matrix;
  applyTableStyle(sheet, matrix.length, matrix[0].length, "OverallTop20");

  const sourceSheet = workbook.worksheets.add("来源概览");
  const sourceHeaders = ["文件", "平台标识", "编码", "记录数", "字段映射"];
  const sourceRows = payload.sources.map((source) => [
    source.file,
    source.platform_key,
    source.encoding,
    source.rows,
    JSON.stringify(source.mapped_fields, null, 0),
  ]);
  const sourceMatrix = [sourceHeaders, ...sourceRows];
  sourceSheet.getRangeByIndexes(0, 0, sourceMatrix.length, sourceMatrix[0].length).values = sourceMatrix;
  applyTableStyle(sourceSheet, sourceMatrix.length, sourceMatrix[0].length, "SourceOverview");
  sourceSheet.getRange("E:E").format.columnWidthPx = 420;

  await workbook.render({ sheetName: "跨平台Top20", autoCrop: "all", scale: 1, format: "png" });
  await workbook.render({ sheetName: "来源概览", autoCrop: "all", scale: 1, format: "png" });
  await exportWorkbook(workbook, payload.outputs.overall_top20);
}

await buildTopByPlatform();
await buildOverallTop20();
