/* 第 3 步：用上一年版本作模板 + 新数据 -> 当年版本 html
 *
 * 用法：
 *     node 3-替换生成新版html.js          # 只预览，不写文件
 *     node 3-替换生成新版html.js --apply  # 确认无误后真正生成
 *
 * 只动两样东西：① base64 数据块  ② 数据区之外的年份文案。
 * 业务逻辑一行不改。
 */
const fs = require('fs');
const path = require('path');

// ==================== CONFIG（每年只改这里） ====================
const YEAR = 2027;
const PREV_YEAR = 2026;
// ===============================================================
const APPLY = process.argv.includes('--apply');

const HERE = __dirname;
const TOOL_DIR = path.resolve(HERE, '..', '..');
const SRC_HTML = path.join(TOOL_DIR, `国考选岗助手-${PREV_YEAR}.html`);
const _outArg = process.argv.find(a => a.startsWith('--out='));
const OUT_HTML = _outArg
  ? path.resolve(_outArg.slice('--out='.length))
  : path.join(TOOL_DIR, `国考选岗助手-${YEAR}.html`);
const B64 = path.join(HERE, `data${YEAR}.b64`);

const src = fs.existsSync(SRC_HTML) ? SRC_HTML : path.join(TOOL_DIR, '国考选岗助手.html');
console.log('模板文件 :', src);
console.log('输出文件 :', OUT_HTML);
console.log('新数据   :', B64);

const s = fs.readFileSync(src, 'utf8');
const newB64 = fs.readFileSync(B64, 'utf8').trim();

// ---- 定位数据块，年份替换只在块外做 ----
const tagStart = s.indexOf('<script id="gkDataB64"');
if (tagStart < 0) throw new Error('模板里没找到 gkDataB64 数据块');
const b64Start = s.indexOf('>', tagStart) + 1;
const b64End = s.indexOf('</script>', b64Start);
console.log(`数据块     : [${b64Start}~${b64End})  原长 ${b64End - b64Start} -> 新长 ${newB64.length}`);

const head = s.slice(0, b64Start);
const tail = s.slice(b64End);

// ---- 一次性年份替换（单次扫描，避免链式误伤）----
const map = { [String(PREV_YEAR)]: String(YEAR), [String(PREV_YEAR - 1)]: String(PREV_YEAR) };
const re = new RegExp(Object.keys(map).join('|'), 'g');
const fix = t => t.replace(re, m => map[m]);

console.log('\n--- 将被替换的位置（数据块之外）---');
let shown = 0;
for (const [n, seg] of [['head', head], ['tail', tail]]) {
  let m;
  const r2 = new RegExp(Object.keys(map).join('|'), 'g');
  while ((m = r2.exec(seg)) !== null) {
    const ctx = seg.slice(Math.max(0, m.index - 70), m.index + 60).replace(/\s+/g, ' ');
    console.log(`  [${n}] ${m[0]} -> ${map[m[0]]}   …${ctx}…`);
    shown++;
  }
}
console.log(`  合计 ${shown} 处`);

const out = fix(head) + newB64 + fix(tail);

// ---- 自检 ----
const cds = out.indexOf('<script id="gkDataB64"');
const cde = out.indexOf('</script>', cds);
const outside = out.slice(0, cds) + out.slice(cde);
const leftOld = outside.split(String(PREV_YEAR - 1)).length - 1;
console.log('\n--- 自检 ---');
console.log('  数据块唯一   :', (out.split('id="gkDataB64"').length - 1) === 1 ? 'OK' : 'FAIL');
console.log(`  残留 ${PREV_YEAR - 1}   :`, leftOld, leftOld === 0 ? 'OK' : '⚠️ 请确认是否为合理引用');
console.log(`  出现 ${YEAR}     :`, outside.split(String(YEAR)).length - 1, '处');
console.log(`  出现 ${PREV_YEAR}     :`, outside.split(String(PREV_YEAR)).length - 1, '处（应为同比引用）');

if (!APPLY) {
  console.log('\n[预览模式] 没有写文件。确认上面的替换位置都对，就加 --apply 重新运行。');
  process.exit(0);
}

// 备份已有同名文件
if (fs.existsSync(OUT_HTML)) {
  const bkDir = path.join(TOOL_DIR, '备份');
  if (!fs.existsSync(bkDir)) fs.mkdirSync(bkDir, { recursive: true });
  const bk = path.join(bkDir, `${path.basename(OUT_HTML, '.html')}-备份-${Date.now()}.html`);
  fs.copyFileSync(OUT_HTML, bk);
  console.log('\n已备份旧文件 ->', bk);
}

fs.writeFileSync(OUT_HTML, out, 'utf8');
console.log('\n已生成 ->', OUT_HTML, `(${(fs.statSync(OUT_HTML).size / 1024 / 1024).toFixed(3)} MB)`);
console.log('\n务必用浏览器打开抽查：条数对不对、点开岗位有没有分、控制台有没有报错。');
