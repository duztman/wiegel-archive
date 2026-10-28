"""Find pairs of horizontal rules with nothing drawn between them (docs/RULES.md: one rule is enough).
Serve hosted/ on :8765, then: python3 tools/double_rules.py main.html "font.html#astrud" about.html
It reads borders, so clip-path (Facts) and the exempt glyph table still show; look before fixing."""
import sys, json
from playwright.sync_api import sync_playwright
JS = r"""() => {
 const R=[], C=[];
 for (const el of document.querySelectorAll('body *')) {
   const cs=getComputedStyle(el); if (cs.display==='none'||cs.visibility==='hidden') continue;
   const r=el.getBoundingClientRect(); if (!r.width) continue;
   const vis=c=>!/rgba\(.*, 0\)$/.test(c) && c!=='transparent';
   const sy=scrollY;
   if (parseFloat(cs.borderTopWidth)>0 && vis(cs.borderTopColor)) R.push({y:r.top+sy,x0:r.left,x1:r.right,el:el.className||el.tagName,side:'top'});
   if (parseFloat(cs.borderBottomWidth)>0 && vis(cs.borderBottomColor)) R.push({y:r.bottom+sy,x0:r.left,x1:r.right,el:el.className||el.tagName,side:'bottom'});
   if (['IMG','CANVAS','INPUT','SELECT','SVG','svg','TEXTAREA'].includes(el.tagName)) C.push({y0:r.top+sy,y1:r.bottom+sy,x0:r.left,x1:r.right});
 }
 const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while (w.nextNode()) { const t=w.currentNode; if (!t.textContent.trim()) continue; const rg=document.createRange(); rg.selectNodeContents(t);
   for (const r of rg.getClientRects()) if (r.width) C.push({y0:r.top+scrollY,y1:r.bottom+scrollY,x0:r.left,x1:r.right}); }
 R.sort((a,b)=>a.y-b.y); const out=[];
 for (let i=0;i<R.length;i++) for (let j=i+1;j<R.length;j++) { const a=R[i],b=R[j]; if (b.y-a.y>90) break; if (b.y-a.y<3) continue;
   const x0=Math.max(a.x0,b.x0), x1=Math.min(a.x1,b.x1); if (x1-x0<40) continue;
   if (!C.some(c=>c.y1>a.y+1&&c.y0<b.y-1&&c.x1>x0&&c.x0<x1)) out.push(`${Math.round(a.y)}→${Math.round(b.y)}  ${a.el}.${a.side} / ${b.el}.${b.side}`); }
 return [...new Set(out)];
}"""
pages = sys.argv[1:]
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1366, 390):
        for u in pages:
            pg = b.new_page(viewport={"width": w, "height": 900}); pg.goto("http://localhost:8765/" + u); pg.wait_for_timeout(2500)
            r = pg.evaluate(JS)
            print(w, u, len(r)); [print("   ", x) for x in r[:12]]
            pg.close()
    b.close()
