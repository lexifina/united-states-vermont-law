"""Bounded, source-faithful forward corrections for Vermont's text audit.

Reads the independent audit inventory, never its wording. Official section DOM
supplies every word. Inline commencement labels and textual tables are retained.
Ambiguous whole-section forms and image-bearing sections are held.
"""
import argparse
import csv
import ctypes
import datetime as dt
import hashlib
import html as escaping
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from lxml import html, etree

HERE = Path(__file__).resolve().parent
COMMON = HERE.parent / 'gitlaw_common'
sys.path.insert(0, str(COMMON))
os.environ['GITLAW_SESSION'] = 'gitlaw-scraper-hp-omen'
os.environ['GIT_NO_LAZY_FETCH'] = '1'
import fetch_scheduler as fs

BLOCKS = {'p','div','li','ul','ol','table','thead','tbody','tfoot','tr','td','th','br','hr',
          'h1','h2','h3','h4','h5','h6','section'}
EMAIL = 'united-states-vermont-law@lexifina.com'
DAY = '2026-11-13'


def normalized(s):
    return ' '.join(s.split())


def flow(node):
    if isinstance(node, NavigableString):
        return str(node)
    if node.name in ('script', 'style'):
        return ''
    s = ''.join(flow(c) for c in node.children)
    return ' '+s+' ' if node.name in BLOCKS else s


def independent_text(node):
    """lxml text extraction, preserving inline adjacency and block boundaries."""
    copy = etree.fromstring(etree.tostring(node), parser=html.HTMLParser())
    for el in copy.iter():
        if el.tag in ('script', 'style'):
            el.text = ''
        elif el.tag in BLOCKS:
            el.text = ' ' + (el.text or '')
            el.tail = ' ' + (el.tail or '')
    return normalized(etree.tostring(copy, method='text', encoding='unicode'))


def identity(heading):
    m = re.match(r'^§\s*([0-9][0-9A-Za-z.\-]*?)\.\s', heading)
    if m:
        return 'section:' + m[1]
    m = re.match(r'^Executive Order No\.\s*([0-9A-Za-z]+(?:-[0-9A-Za-z]+)*)', heading)
    return 'eo:' + m[1] if m else None


def forms_bs(raw, target):
    soup = BeautifulSoup(raw, 'html.parser')
    result = []
    for li in soup.select('ul.statutes-list li, ul.statutes-detail li'):
        div = li.find('div', recursive=False)
        if div is None:
            continue
        p = next((p for p in div.find_all('p') if p.get_text(strip=True)), None)
        if p is not None and identity(normalized(flow(p))) == target:
            result.append((li, div, p))
    return result


def forms_lxml(raw, target):
    tree = html.fromstring(raw)
    result = []
    for li in tree.xpath("//ul[contains(concat(' ',normalize-space(@class),' '),' statutes-list ') or "
                         "contains(concat(' ',normalize-space(@class),' '),' statutes-detail ')]//li"):
        for div in li.xpath('./div'):
            p = next((p for p in div.xpath('.//p') if normalized(''.join(p.itertext()))), None)
            if p is not None and identity(independent_text(p)) == target:
                result.append(li)
    return result


def render(div, first):
    """Plain paragraphs, plus intact HTML for textual tables; no OCR or word fixes."""
    parts = []
    pending = []
    def flush():
        s = normalized(''.join(pending))
        pending.clear()
        if s:
            parts.append(s)
    def walk(node):
        if node is first:
            return
        if isinstance(node, NavigableString):
            pending.append(str(node))
            return
        if node.name in ('script','style'):
            return
        if node.name == 'table':
            flush()
            parts.append(str(node))
            return
        if node.name in BLOCKS:
            flush()
        for child in node.children:
            walk(child)
        if node.name in BLOCKS:
            flush()
    for child in div.children:
        walk(child)
    flush()
    return '# ' + normalized(flow(first)) + '\n\n' + '\n\n'.join(parts) + '\n'


def rendered_text(text):
    chunks = re.split(r'(<table\b.*?</table>)', text.removeprefix('# '), flags=re.S)
    raw = '<div>' + ''.join(c if c.startswith('<table') else escaping.escape(c) for c in chunks) + '</div>'
    return independent_text(html.fromstring(raw))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def run(args, job, cwd=None, env=None):
    p = subprocess.Popen(args, cwd=cwd, env=env, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with (job/'pids.txt').open('a', encoding='utf-8') as f:
        f.write(str(p.pid)+' '+args[0]+'\n')
    try:
        out, err = p.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        raise
    if p.returncode:
        raise RuntimeError(f'{args[0]} exit {p.returncode}: {err.decode("utf-8", "replace")[:1500]}')
    return out.decode('utf-8').strip()


def get_source(url, job, manifest):
    if url in manifest:
        row=manifest[url]
        content=job/'source-evidence'/row.get('sha256','')
        if content.is_file():
            raw=content.read_bytes()
            if hashlib.sha256(raw).hexdigest()==row['sha256']:
                return raw
        legacy=job/'source-evidence'/hashlib.sha256(url.encode()).hexdigest()
        raw=legacy.read_bytes()
        if 'sha256' in row:
            assert hashlib.sha256(raw).hexdigest()==row['sha256'],url
        return raw
    for attempt in range(3):
        try:
            raw = fs.get(url, cache=job/'source-evidence', tries=1, wait=False, caller='q-1905')
            code = fs.last_status()
            if code in (403,429):
                raise fs.HostStopped(f'HTTP {code}: {url}')
            if raw is not None:
                manifest[url] = {'url':url,'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw),
                                 'http_status':code,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat()}
                save(job/'source-evidence'/'manifest.json', list(manifest.values()))
                return raw
            if code in (404,410):
                raise ValueError(f'HTTP {code}')
        except fs.NotNow as e:
            seconds = e.at-time.time()
            if seconds > 900:
                raise
            print(f'Waiting {max(0,seconds):.1f}s for scheduler', flush=True)
            while time.time() < e.at:
                time.sleep(min(30, max(.05,e.at-time.time())))
            return get_source(url, job, manifest)
        if attempt < 2:
            time.sleep(120)
    raise ValueError('No body after three attempts')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--inventory',type=Path,required=True)
    ap.add_argument('--baseline-corpus',type=Path,required=True)
    ap.add_argument('--prepare-only',action='store_true')
    ap.add_argument('--out',default='input')
    args = ap.parse_args()
    job=args.job
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    with (job/'pids.txt').open('a') as f:
        f.write(str(os.getpid())+' repair_fulltext.py\n')
    if __import__('shutil').disk_usage('C:/').free < 40*1024**3:
        raise RuntimeError('retry later: disk below 40 GiB')
    repo=job/'published'
    base=run(['git','rev-parse','origin/main'],job,repo)
    assert run(['git','status','--porcelain'],job,repo)==''
    corpus=json.loads(args.baseline_corpus.read_text(encoding='utf-8'))
    acts={a['slug']:a for a in corpus['acts']}
    manifest={}
    manifest_path=job/'source-evidence'/'manifest.json'
    if manifest_path.exists():
        manifest={r['url']:r for r in json.loads(manifest_path.read_text(encoding='utf-8'))}
    robots=get_source('https://legislature.vermont.gov/robots.txt',job,manifest)
    listing=get_source('https://legislature.vermont.gov/statutes',job,manifest)
    titles=sorted(set(re.findall(r'href=[\"\'](/statutes/title/[^\"\']+)',listing.decode('utf-8'))))
    known={a['url'].split('legislature.vermont.gov')[-1] for a in corpus['acts']}
    save(job/'source-evidence'/'listing-check.json',{'titles':len(titles),'missing':sorted(set(titles)-known),
         'robots':robots.decode('utf-8','replace'), 'host':fs.host_report('legislature.vermont.gov')})
    rows=list(csv.DictReader(args.inventory.open(encoding='utf-8',newline=''),delimiter='\t'))
    grouped=defaultdict(list)
    for row in rows:
        grouped[row['act']].append(row)
    accepted=[];held=[];already=[];batches=[]
    for slug, candidates in sorted(grouped.items()):
        act=acts[slug]
        current=max((v for v in act['versions'] if v['from']<=DAY),key=lambda v:v['from'])
        batch=[]
        for row in candidates:
            if slug=='constitution':
                held.append({**row,'reason':'Constitution structural boundaries require separate parser'})
                continue
            path=row['file']; key=path[len(slug)+1:-3]
            original=(run(['git','show',base+':'+path],job,repo)+'\n' if args.prepare_only
                      else (repo/path).read_text(encoding='utf-8'))
            target=identity(original.splitlines()[0].removeprefix('# '))
            try:
                raw=get_source(row['url'],job,manifest)
                bs=forms_bs(raw,target); lx=forms_lxml(raw,target)
                if len(bs)!=1 or len(lx)!=1:
                    raise ValueError(f'ambiguous source forms: {len(bs)}/{len(lx)}')
                li,div,first=bs[0]
                heading=normalized(flow(first))
                if re.search(r'\[(?:Effective|Repealed|Contingently)',heading,re.I):
                    raise ValueError('whole-section effective/repeal form requires timing review')
                if li.find('img') is not None:
                    raise ValueError('image-bearing section requires asset survey')
                text=render(div,first)
                source_bs=normalized(flow(li));source_lx=independent_text(lx[0])
                rendered=rendered_text(text)
                if not (source_bs==source_lx==rendered):
                    raise ValueError('independent DOM/rendered text mismatch')
                if text==original:
                    already.append(path);continue
                if key not in current['units']:
                    raise ValueError('unit absent from baseline corpus')
                current['units'][key]['text']=text
                record={'file':path,'url':row['url'],'source_sha256':hashlib.sha256(raw).hexdigest(),
                        'characters':len(source_bs),'tables':len(li.find_all('table')),'source_images':0,
                        'inline_effective_labels':len(re.findall(r'\[(?:Sub[^\]]*effective|Sub[^\]]*repealed)',source_bs,re.I))}
                accepted.append(record);batch.append(record)
            except (fs.HostStopped,fs.HostDailyCap,fs.NotNow):
                raise
            except Exception as e:
                held.append({**row,'reason':str(e)})
        out=job/args.out
        save(out/'checked.json',{'accepted':accepted,'held':held,'already_equal':already})
        out.mkdir(parents=True,exist_ok=True)
        (out/'corpus.json').write_text(json.dumps(corpus,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        if batch and not args.prepare_only:
            import append
            head=run(['git','rev-parse','HEAD'],job,repo)
            plans=append.plan_corrections(repo,{**corpus,'acts':[act]},head,
                         {slug:current['from']},'restore full official text, textual tables, notes and printed effective-date labels')
            expected={r['file'] for r in batch}
            actual={f for x in plans for f in x['files']}
            assert actual==expected,(slug,len(actual),len(expected))
            for plan in plans:
                for path,text in plan['files'].items():
                    assert text is not None
                    (repo/path).write_text(text,encoding='utf-8',newline='\n')
                msg,trailers=append.correction_message(corpus,plan)
                trailers.append('In-force-basis: Existing published snapshot date '+current['from']+
                                ' retained for a text correction; title-wide source dating remains under review.')
                (job/'commit-message.txt').write_text('\n'.join(msg).rstrip()+'\n\n'+'\n'.join(trailers)+'\n',encoding='utf-8')
                env=os.environ.copy();env.update(GIT_AUTHOR_NAME='Lexifina',GIT_COMMITTER_NAME='Lexifina',
                            GIT_AUTHOR_EMAIL=EMAIL,GIT_COMMITTER_EMAIL=EMAIL)
                run(['git','add','--',*sorted(plan['files'])],job,repo)
                run(['git','-c','gc.auto=0','commit','--no-gpg-sign','-F',str(job/'commit-message.txt')],job,repo,env)
            batches.append({'act':slug,'sections':len(batch),'head':run(['git','rev-parse','HEAD'],job,repo)})
            save(job/'source-evidence'/'streamed-batches.json',batches)
        print(f'{slug}: accepted {len(batch)}, total {len(accepted)}, held {len(held)}',flush=True)
    save(job/'source-evidence'/'summary.json',{'baseline':base,'candidates':len(rows),'accepted':len(accepted),
          'held':len(held),'already_equal':len(already),'acts':len({r['file'].split('/')[0] for r in accepted}),
          'source_pages':len(manifest),'batches':batches})


if __name__=='__main__':
    main()
