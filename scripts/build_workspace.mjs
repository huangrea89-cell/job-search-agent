import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath, previewDir] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error("usage: build_workspace.mjs SNAPSHOT OUTPUT [PREVIEW_DIR]");
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();

const colors = { navy: "#16324F", blue: "#2563EB", pale: "#EAF2FF", green: "#DCFCE7", amber: "#FEF3C7", red: "#FEE2E2", gray: "#64748B", line: "#D6DEE8", white: "#FFFFFF" };
const header = (sheet, range) => {
  range.format.fill = colors.navy;
  range.format.font = { bold: true, color: colors.white };
  range.format.wrapText = true;
  range.format.rowHeight = 30;
  range.format.borders = { preset: "outside", style: "thin", color: colors.navy };
};
const body = (range) => {
  range.format.font = { color: "#172033", size: 10 };
  range.format.verticalAlignment = "center";
  range.format.wrapText = true;
  range.format.borders = { insideHorizontal: { style: "thin", color: colors.line } };
  range.format.autofitRows();
};
const setup = (sheet, freezeRows = 1) => {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(freezeRows);
};
const text = value => Array.isArray(value) ? value.join("；") : (value ?? "");

const main = workbook.worksheets.add("岗位主表");
setup(main, 5);
main.getRange(data.demo ? "A1:M1" : "A1:Q1").merge();
main.getRange("A1").values = [[data.demo ? "求职 Agent · 虚构岗位演示" : "求职 Agent · 岗位工作台"]];
main.getRange("A1:Q1").format.fill = colors.navy;
main.getRange("A1:Q1").format.font = { bold: true, color: colors.white, size: 18 };
main.getRange("A1:Q1").format.rowHeight = 38;
main.getRange("A2").values = [["展示岗位"]];
main.getRange("B2").formulas = [["=COUNTA(A6:A505)"]];
main.getRange("D2").values = [["五星岗位"]];
main.getRange("E2").formulas = [["=COUNTIF(B6:B505,5)"]];
main.getRange("G2").values = [["待确认"]];
main.getRange("H2").formulas = [["=ROWS(M6:M505)-COUNTBLANK(M6:M505)"]];
main.getRange("A2:H2").format.fill = colors.pale;
main.getRange("A2:H2").format.font = { bold: true, color: colors.navy };
main.getRange("A3").values = [[data.demo ? "演示数据" : "更新岗位"]];
main.getRange("B3:C3").merge();
main.getRange("B3").values = [[data.demo ? "examples/demo.json" : data.control_url]];
main.getRange("D3:H3").merge();
main.getRange("D3").values = [[data.demo ? "全部虚构；只读快照；简历操作已停用。" : "SQLite 是数据真源；请勿把本表编辑当作数据库更新。状态变更请使用本地控制台。"]];
main.getRange("A3:H3").format.fill = colors.amber;
const mainHeaders = ["岗位ID","星级","公司","岗位","地点","工作形式","发布时间","首次发现","总分","期望分","履历分","可信度","校招资格/待确认","推荐理由","用户状态","来源","简历操作"];
main.getRange("A5:Q5").values = [mainHeaders]; header(main, main.getRange("A5:Q5"));
const visible = data.jobs.filter(j => !j.filtered && !j.hidden && Number(j.stars) >= 2);
if (visible.length) {
  main.getRangeByIndexes(5, 0, visible.length, 17).values = visible.map(j => [j.id,j.stars,j.company,j.title,text(j.accepted_locations),j.employment_type,j.published_at,j.first_seen_at,j.total_score,j.expectation_score,j.resume_score,j.confidence,text(j.needs_confirmation),j.recommendation,j.user_status,j.source_url,""]);
  visible.forEach((j,i)=> {
    const cell = main.getRangeByIndexes(5+i,16,1,1);
    if (data.demo) cell.values = [[j.resume_proposal_id ? "示例方案待确认" : "演示不执行操作"]];
    else cell.formulas=[[`=HYPERLINK("${data.control_url}?job_id=${j.id}","${j.resume_proposal_id ? "查看简历方案" : "生成简历方案"}")`]];
  });
  body(main.getRangeByIndexes(5, 0, visible.length, 17));
}
main.getRange("A6:A25").format.numberFormat = "0";
main.getRange("G6:H25").format.numberFormat = "yyyy-mm-dd hh:mm";
main.getRange("B6:B25").conditionalFormats.add("colorScale", { colors: [colors.red, colors.amber, colors.green] });
main.getRange("O6:O25").dataValidation = { rule: { type: "list", values: ["unprocessed","interested","preparing","applied","not_interested"] } };
[9,8,18,24,12,12,13,18,8,8,8,10,36,28,16,36,18].forEach((w,i)=>main.getRangeByIndexes(0,i,Math.max(6,visible.length+5),1).format.columnWidth=w);

const history = workbook.worksheets.add("每日更新历史"); setup(history);
const histHeaders = ["运行ID","开始时间","结束时间","状态","检查来源","来源结果","新增","变化","关闭","过滤"];
history.getRange("A1:J1").values=[histHeaders]; header(history,history.getRange("A1:J1"));
if(data.update_runs.length){history.getRangeByIndexes(1,0,data.update_runs.length,10).values=data.update_runs.map(r=>[r.id,r.started_at,r.finished_at,r.status,text(r.requested_sources),Object.entries(r.source_results).map(([name,value])=>`${name}: ${value.status}`).join("；"),r.added_count,r.changed_count,r.closed_count,r.filtered_count]);body(history.getRangeByIndexes(1,0,data.update_runs.length,10));history.getRangeByIndexes(1,1,data.update_runs.length,2).format.numberFormat="yyyy-mm-dd hh:mm";}
[8,20,20,12,22,52,9,9,9,9].forEach((w,i)=>history.getRangeByIndexes(0,i,Math.max(2,data.update_runs.length+1),1).format.columnWidth=w);

const filtered = workbook.worksheets.add("已过滤岗位"); setup(filtered);
const filterHeaders=["岗位ID","公司","岗位","地点","星级","总分","过滤原因","关键差距","来源"];
filtered.getRange("A1:I1").values=[filterHeaders];header(filtered,filtered.getRange("A1:I1"));
const removed=data.jobs.filter(j=>j.filtered || Number(j.stars)<2 || j.status==="closed");
if(removed.length){filtered.getRangeByIndexes(1,0,removed.length,9).values=removed.map(j=>[j.id,j.company,j.title,text(j.accepted_locations),j.stars,j.total_score,text(j.reasons),text(j.gaps),j.source_url]);body(filtered.getRangeByIndexes(1,0,removed.length,9));}
[9,18,24,12,8,8,32,32,36].forEach((w,i)=>filtered.getRangeByIndexes(0,i,Math.max(2,removed.length+1),1).format.columnWidth=w);

const hidden = workbook.worksheets.add("永久隐藏"); setup(hidden);
hidden.getRange("A1:F1").values=[["岗位ID","公司","岗位","用户状态","最后状态","来源"]];header(hidden,hidden.getRange("A1:F1"));
const hiddenRows=data.jobs.filter(j=>j.user_status==="not_interested");
if(hiddenRows.length){hidden.getRangeByIndexes(1,0,hiddenRows.length,6).values=hiddenRows.map(j=>[j.id,j.company,j.title,j.user_status,j.status,j.source_url]);body(hidden.getRangeByIndexes(1,0,hiddenRows.length,6));}
[9,20,26,18,14,40].forEach((w,i)=>hidden.getRangeByIndexes(0,i,Math.max(2,hiddenRows.length+1),1).format.columnWidth=w);

const applications = workbook.worksheets.add("投递记录"); setup(applications);
applications.getRange("A1:I1").values=[["记录ID","公司","岗位","状态","投递时间","简历版本","备注","创建时间","更新时间"]];header(applications,applications.getRange("A1:I1"));
if(data.applications.length){applications.getRangeByIndexes(1,0,data.applications.length,9).values=data.applications.map(a=>[a.id,a.company,a.title,a.status,a.applied_at,a.resume_version,a.notes,a.created_at,a.updated_at]);body(applications.getRangeByIndexes(1,0,data.applications.length,9));}
[9,20,26,18,18,16,32,20,20].forEach((w,i)=>applications.getRangeByIndexes(0,i,Math.max(2,data.applications.length+1),1).format.columnWidth=w);

// Refit only after final column widths are known.
for (const sheet of [main, history, filtered, hidden, applications]) {
  sheet.getUsedRange().format.font.name = "Arial";
  sheet.getUsedRange().format.autofitRows();
}
main.getRange("A1:Q1").format.rowHeight = 38;
main.getRange("A2:H3").format.wrapText = true;
main.getRange("A2:H3").format.rowHeight = 32;
if (data.demo) {
  main.getRange("A5:Q5").format.rowHeight = 30;
  if (visible.length) main.getRangeByIndexes(5, 0, visible.length, 17).format.rowHeight = 48;
  for (const [sheet, count, label] of [[history, data.update_runs.length, "本次演示无更新运行记录"], [hidden, hiddenRows.length, "本次演示无永久隐藏岗位"], [applications, data.applications.length, "本次演示未进行投递"]]) {
    if (!count) { sheet.getRange("A2:F2").merge(); sheet.getRange("A2").values = [[label]]; sheet.getRange("A2:F2").format.rowHeight = 30; }
  }
}
workbook.recalculate();
if (data.demo) {
  const expected = [visible.length, visible.filter(j => j.stars === 5).length, visible.filter(j => text(j.needs_confirmation)).length];
  const actual = ["B2", "E2", "H2"].map(address => main.getRange(address).values[0][0]);
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error("Demo summary does not reconcile with source records");
}
const checks = await workbook.inspect({ kind: "table", range: "岗位主表!A1:Q8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 17, maxChars: 3500 });
console.log(checks.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula errors" });
console.log(errors.ndjson);
if (previewDir) {
  await fs.mkdir(previewDir,{recursive:true});
  for (const sheetName of ["岗位主表","每日更新历史","已过滤岗位","永久隐藏","投递记录"]) {
    const png=await workbook.render({sheetName,autoCrop:"all",scale:1,format:"png"});
    await fs.writeFile(`${previewDir}/${sheetName}.png`,new Uint8Array(await png.arrayBuffer()));
  }
  if (data.demo) {
    const png = await workbook.render({sheetName:"岗位主表",range:`A1:M${visible.length+5}`,scale:1.5,format:"png"});
    await fs.writeFile(`${previewDir}/workspace.png`,new Uint8Array(await png.arrayBuffer()));
  }
}
await fs.mkdir(path.dirname(outputPath),{recursive:true});
const output=await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
