/* 第 2 步：raw JSON -> 内嵌数据（gzip + base64），并算好同比 prevNum
 *
 * 用法：改下面 CONFIG 区，然后
 *     node 2-生成内嵌数据.js
 *
 * 设计要点：解析函数不重写，而是**从上一年的 html 里原样抽取**再执行，
 * 这样页面逻辑一改，脚本自动跟随，不会出现两套逻辑不一致。
 */
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const vm = require('vm');

// ==================== CONFIG（每年只改这里） ====================
const YEAR = 2027;                                    // 当年
const PREV_YEAR = 2026;                               // 上一年
const HERE = __dirname;
const TOOL_DIR = path.resolve(HERE, '..', '..');      // 国考选岗助手/

// 上一年版本的文件名（优先带年份后缀的，其次无后缀的老版）
const PREV_HTML = [
  path.join(TOOL_DIR, `国考选岗助手-${PREV_YEAR}.html`),
  path.join(TOOL_DIR, '国考选岗助手.html'),
].find(p => fs.existsSync(p));
const CODE_SRC_HTML = PREV_HTML;   // 解析函数就从它抽
// ===============================================================

const RAW = path.join(HERE, `raw${YEAR}.json`);
const OUT_B64 = path.join(HERE, `data${YEAR}.b64`);

/* ---------- 1) 从 html 抽取解析函数 ---------- */
function extractParsers(html) {
  const A1 = '/* ===================== 解析与归一化（导入新表时复用） ===================== */';
  const A2 = '/* ===================== 匹配逻辑 ===================== */';
  const a = html.indexOf(A1), b = html.indexOf(A2);
  if (a < 0 || b < 0 || b <= a) throw new Error('没找到 HTML 里的「解析与归一化」代码区，页面结构可能变了');
  const region = html.slice(a, b);

  const pm = html.match(/const PROVS\s*=\s*\[[^\]]*\];/);
  if (!pm) throw new Error('没找到 const PROVS 定义');
  return pm[0] + '\n' + region;
}

function loadHtml(p) {
  if (!fs.existsSync(p)) throw new Error('找不到页面文件：' + p);
  return fs.readFileSync(p, 'utf8');
}

/* ---------- 2) 从页面 dump 内嵌数据 ---------- */
function dumpEmbedded(html) {
  const tagStart = html.indexOf('<script id="gkDataB64"');
  if (tagStart < 0) throw new Error('没找到 gkDataB64 数据块');
  const s = html.indexOf('>', tagStart) + 1;
  const e = html.indexOf('</script>', s);
  const b64 = html.slice(s, e).trim();
  return JSON.parse(zlib.gunzipSync(Buffer.from(b64, 'base64')).toString('utf8'));
}

/* ---------- 3) 跑起来 ---------- */
const prevHtml = loadHtml(PREV_HTML);
const codeHtml = loadHtml(CODE_SRC_HTML);

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(extractParsers(codeHtml), sandbox);
['extractProv', 'parseSG', 'isFresh', 'clean', 'parseCats', 'parseCodes', 'norm'].forEach(f => {
  if (typeof sandbox[f] !== 'function') throw new Error('抽取后缺少函数：' + f);
});
const norm = sandbox.norm;

const prevData = dumpEmbedded(prevHtml);
console.log(`上一年（${PREV_YEAR}）内嵌 ${prevData.length} 条，来自 ${path.basename(PREV_HTML)}`);

const cl = x => String(x == null ? '' : x).replace(/\s+/g, '').trim();
const keyPrev = r => [r.dept, r.bureau, r.code].map(cl).join('|');
const keyThis = r => [r['部门名称'], r['用人司局'], r['职位代码']].map(cl).join('|');

// 上一年： 部门名称|用人司局|职位代码 -> 招录人数合计
const idx = new Map();
for (const r of prevData) {
  const k = keyPrev(r);
  idx.set(k, (idx.get(k) || 0) + (Number(r.num) || 0));
}

// 字段集与顺序必须与上一年的内嵌数据一致
const FIELD_ORDER = Object.keys(prevData[0]);

const raw = JSON.parse(fs.readFileSync(RAW, 'utf8'));
const out = [];
let hit = 0;
for (let i = 0; i < raw.length; i++) {
  const r = raw[i];
  const n = norm(r, i, YEAR, r._sheet);
  const k = keyThis(r);
  n.prevNum = idx.has(k) ? idx.get(k) : null;
  if (n.prevNum !== null) hit++;
  const slim = {};
  for (const f of FIELD_ORDER) slim[f] = n[f];
  out.push(slim);
}

const keys = Object.keys(out[0]).join(',');
const prevKeys = Object.keys(prevData[0]).join(',');
if (keys !== prevKeys) throw new Error(`字段集与上一年不一致！\n当年: ${keys}\n上年: ${prevKeys}`);

console.log(`当年（${YEAR}）生成 ${out.length} 条`);
console.log(`同比覆盖 ${hit} 条（${(hit / out.length * 100).toFixed(2)}%）`);
console.log(`字段集与上一年一致：OK（${Object.keys(out[0]).length} 个）`);

const json = JSON.stringify(out);
const b64 = zlib.gzipSync(Buffer.from(json, 'utf8'), { level: 6 }).toString('base64');

const back = JSON.parse(zlib.gunzipSync(Buffer.from(b64, 'base64')).toString('utf8'));
if (back.length !== out.length) throw new Error('回环校验失败');

fs.writeFileSync(OUT_B64, b64);
console.log(`gzip+base64 长度 ${b64.length} -> ${OUT_B64}`);
console.log();
console.log('下一步：跑 3-替换生成新版html.js');
