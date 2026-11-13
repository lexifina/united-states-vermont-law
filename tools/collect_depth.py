"""Source-gated append-only Vermont title date/punctuation review.

All fetches use the shared scheduler. Official HTML is the independent text
reference; inherited law files supply layout only. Non-punctuation disagreement
or ambiguous forms hold the title. Never pushes or writes publication markers.
"""
import argparse
import ctypes
import datetime as dt
import hashlib
import html as escaping
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from lxml import etree, html
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
os.environ.update(GITLAW_SESSION='gitlaw-scraper-hp-omen', GIT_NO_LAZY_FETCH='1',
                  GIT_AUTHOR_NAME='Lexifina', GIT_COMMITTER_NAME='Lexifina',
                  GIT_AUTHOR_EMAIL='united-states-vermont-law@lexifina.com',
                  GIT_COMMITTER_EMAIL='united-states-vermont-law@lexifina.com')
import fetch_scheduler as fs

BLOCKS = {'p','div','li','ul','ol','table','thead','tbody','tfoot','tr','td','th','br','hr',
          'h1','h2','h3','h4','h5','h6','section'}
DATE = re.compile(r'(?i)\b(?:eff\.|effective(?:\s+on)?)\s+([A-Za-z]+)\.?\s+(\d{1,2}),\s*((?:19|20)\d\d)')
MONTHS = {name.lower(): i for i in range(1,13) for name in
          (dt.date(2000,i,1).strftime('%B'),dt.date(2000,i,1).strftime('%b'))}
MONTHS['sept'] = 9

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def norm(s): return ' '.join(s.split())

def source_text(node):
    parts=[]
    for event, el in etree.iterwalk(node, events=('start','end')):
        if event=='start':
            if el.tag in BLOCKS: parts.append(' ')
            if el.text: parts.append(el.text)
        else:
            if el.tag in BLOCKS: parts.append(' ')
            if el.tail: parts.append(el.tail)
    return norm(''.join(parts))

def bs_text(node):
    from bs4 import NavigableString
    if isinstance(node,NavigableString): return str(node)
    s=''.join(bs_text(c) for c in node.children)
    return ' '+s+' ' if node.name in BLOCKS else s

def output_text(s):
    s=s.removeprefix('# ');parts=[];at=0
    for m in re.finditer(r'<table\b.*?</table>',s,re.S):
        parts.extend([escaping.escape(s[at:m.start()]),m.group()]);at=m.end()
    parts.append(escaping.escape(s[at:]))
    return source_text(html.fromstring('<section>'+''.join(parts)+'</section>'))

def number(s):
    m=re.match(r'^§\s*([0-9][0-9A-Za-z.\-]*?)\.\s',s)
    return m[1] if m else None

def unit_key(n):
    m=re.match(r'^(\d+)(.*)$',n)
    return 'sec-'+m[1].zfill(4)+m[2]

def noncurrent_notice(block):
    """Printed status notices, including a redesignation with no operative body."""
    return bool(re.search(r'\b(?:Repealed|Omitted|Reserved)\b',block['heading'])) or (
        'Redesignated.' in block['heading'] and block['text']==block['heading'])

def disk():
    if shutil.disk_usage('C:/').free < 40*1024**3: raise RuntimeError('retry later: disk below 40 GiB')

def run(cmd,job,cwd=None):
    p=subprocess.Popen(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    with (job/'pids.txt').open('a') as f:f.write(f'{p.pid} {cmd[0]}\n')
    try: out,err=p.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        p.kill();p.communicate();raise
    if p.returncode:raise RuntimeError(err.decode('utf8','replace'))
    return out.decode('utf8').strip()

def repo_path(job):
    pointer=job/'candidate-path.txt'
    return Path(pointer.read_text(encoding='utf8').strip()) if pointer.exists() else job/'published'

def git(job,*args):return run(['git','-C',str(repo_path(job)),*args],job)

def fetch(url,job,refresh=False):
    disk();attempt=0
    while attempt<3:
        try:
            raw=fs.get(url,cache=job/'cache',tries=1,wait=False,refresh=refresh,
                       caller=job.name+'-vermont-depth')
            code=fs.last_status()
            if code in (403,429):raise fs.HostStopped(f'HTTP {code}: {url}')
            if raw:
                sha=hashlib.sha256(raw).hexdigest();(job/'source-evidence'/sha).write_bytes(raw)
                return {'url':url,'sha256':sha,'bytes':len(raw),'status':code,
                        'checked_at':dt.datetime.now(dt.timezone.utc).isoformat()}
            if code in (404,410):raise ValueError(f'HTTP {code}: {url}')
            attempt+=1
        except fs.NotNow as e:
            if e.at-time.time()>900:raise
            print('scheduler wait',max(0,e.at-time.time()),flush=True)
            while time.time()<e.at:time.sleep(min(30,max(.1,e.at-time.time())))
            continue
        if attempt<3:time.sleep(120)
    raise ValueError('no body after 3 retries: '+url)

def official(job,title):
    rows=json.loads((job/'source-evidence'/f'fetched-{title}.json').read_text(encoding='utf8'))
    listing_raw=(job/'source-evidence'/rows[0]['sha256']).read_bytes()
    assert hashlib.sha256(listing_raw).hexdigest()==rows[0]['sha256']
    expected={'https://legislature.vermont.gov'+p.replace('/statutes/chapter/','/statutes/fullchapter/') for p in
              html.fromstring(listing_raw).xpath('//a[starts-with(@href,"/statutes/chapter/")]/@href')}
    assert expected and expected=={row['url'] for row in rows[1:]},('chapter listing incomplete',title)
    blocks={};groups={};dates=[];images=[];notes=[]
    for row in rows[1:]:
        raw=(job/'source-evidence'/row['sha256']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row['sha256']
        tree=html.fromstring(raw);bs=BeautifulSoup(raw,'html.parser');bs_blocks={}
        previous=HERE/'.cache'/(hashlib.sha256(row['url'].encode()).hexdigest()+'.bin')
        if previous.exists():
            oldtree=html.fromstring(previous.read_bytes())
            selector='//ul[contains(@class,"statutes-list") or contains(@class,"statutes-detail")]'
            assert [source_text(n) for n in tree.xpath(selector)]==[source_text(n) for n in oldtree.xpath(selector)],('official capture drift',row['url'])
        for li in bs.select('ul.statutes-list li, ul.statutes-detail li'):
            div=li.find('div',recursive=False)
            if div is None:continue
            p=next((p for p in div.find_all('p') if p.get_text(strip=True)),None)
            if p is None:continue
            n=number(norm(bs_text(p)))
            if n:
                bs_blocks.setdefault(n,[]).append(norm(bs_text(li)))
        seen=set();positions={}
        for li in tree.xpath('//ul[contains(@class,"statutes-list") or contains(@class,"statutes-detail")]//li'):
            first=next((p for p in li.xpath('./div//p') if ''.join(p.itertext()).strip()),None)
            if first is None:continue
            n=number(source_text(first))
            if not n:continue
            seen.add(n);s=source_text(li)
            at=positions.get(n,0);positions[n]=at+1
            assert s==bs_blocks[n][at],('two parser disagreement',n)
            groups.setdefault(n,[]).append({'text':s,'url':row['url'],'heading':source_text(first)})
            for img in li.xpath('.//img|.//svg|.//object|.//embed|.//canvas|.//*[@style and contains(@style,"url(")]'):
                images.append({'section':n,'url':row['url'],'element':img.tag,
                               'image':img.get('src') or img.get('data') or img.get('style')})
            for m in DATE.finditer(s):
                day=dt.date(int(m[3]),MONTHS[m[1].lower()],int(m[2])).isoformat()
                dates.append({'section':n,'day':day,'quote':m.group(),
                              'context':s[max(0,m.start()-150):min(len(s),m.end()+50)],'url':row['url']})
            if re.search(r'\b(?:2025|2026),\s*No\.',s):notes.append({'section':n,'history':s[-900:],'url':row['url']})
        assert seen==set(bs_blocks) and all(positions[n]==len(bs_blocks[n]) for n in seen),('section sets differ',row['url'])
    for n,forms in groups.items():
        if len(forms)==1:blocks[n]=forms[0];continue
        repealed=[b for b in forms if '[Repealed]' in b['heading']]
        assert len(repealed)==1,('ambiguous source forms',n)
        for b in forms:
            m=re.search(r'repealed on ([A-Za-z]+) (\d{1,2}), (20\d\d) by',b['text'])
            assert m and dt.date(int(m[3]),MONTHS[m[1].lower()],int(m[2])).isoformat()<='2026-11-02',('ambiguous source repeal',n)
        blocks[n]={**repealed[0],'superseded_source_forms':[b for b in forms if b is not repealed[0]]}
    return rows,blocks,dates,images,notes

def audit(job,title):
    rows,blocks,dates,images,notes=official(job,title)
    slug='title-'+str(int(title));r=repo_path(job)/slug
    existing={p.stem:p for p in r.glob('sec-*.md')}
    missing=[];matches=[];mismatches=[]
    for n,b in blocks.items():
        k=unit_key(n)
        if k not in existing:missing.append({'section':n,'text':b['text'],'url':b['url']});continue
        old=existing[k].read_text(encoding='utf8')
        row={'file':slug+'/'+k+'.md','section':n,'equal':output_text(old)==b['text']}
        (matches if row['equal'] else mismatches).append(row)
    result={'title':title,'pages':len(rows)-1,'source_sections':len(blocks),'published_units':len(existing),
            'matches':matches,'mismatches':mismatches,'missing':missing,'images':images,'dates':dates,'recent_notes':notes,
            'extra_published':sorted(set(existing)-{unit_key(n) for n in blocks})}
    save(job/'source-evidence'/f'audit-{title}.json',result)
    print('AUDIT',title,'pages',len(rows)-1,'units',len(existing),'equal',len(matches),'mismatch',len(mismatches),
          'missing',len(missing),'images',len(images),'latest',max((d['day'] for d in dates if d['day']<='2026-11-13'),default=None),flush=True)
    return result

def fetch_title(job,title):
    row=fetch('https://legislature.vermont.gov/statutes/title/'+title,job)
    raw=(job/'source-evidence'/row['sha256']).read_bytes()
    tree=html.fromstring(raw)
    paths=sorted(set(p.replace('/statutes/chapter/','/statutes/fullchapter/') for p in
                     tree.xpath('//a[starts-with(@href,"/statutes/chapter/")]/@href')))
    assert paths and all(p.startswith('/statutes/fullchapter/'+title+'/') for p in paths),paths
    rows=[row];save(job/'source-evidence'/f'fetched-{title}.json',rows)
    held=[]
    for path in paths:
        try:rows.append(fetch('https://legislature.vermont.gov'+path,job))
        except ValueError as e:held.append({'url':path,'reason':str(e)})
        save(job/'source-evidence'/f'fetched-{title}.json',rows)
        print('FETCH',title,len(rows)-1,'/',len(paths),path,flush=True)
    save(job/'source-evidence'/f'fetch-held-{title}.json',held)
    if not held:return audit(job,title)
    return {'held':held}

def build_title(job,title,day,baseline,intermediate=False):
    import append, build, private
    disk();r=repo_path(job);e=job/'source-evidence';i=job/'input';i.mkdir(exist_ok=True)
    slug='title-'+str(int(title));head=git(job,'rev-parse','HEAD')
    assert not git(job,'status','--porcelain')
    prior=(i/'corpus.json') if (i/'corpus.json').exists() else baseline
    raw=prior.read_bytes();assert hashlib.sha256(raw).hexdigest()==(r/'data/corpus.sha256').read_text().split()[0]
    corpus=json.loads(raw);act=next(a for a in corpus['acts'] if a['slug']==slug)
    assert len(act['versions'])==1
    version=act['versions'][0];old=version['from'];assert old=='2026-11-02' and day<old
    rows,blocks,dates,images,notes=official(job,title)
    assert images==[],'normative images require separate review'
    assert max(d['day'] for d in dates if d['day']<='2026-11-13')==day
    proof=[];changes=[];edits=[];removals=[]
    for k in list(version['units']):
        n=next(n for n in blocks if unit_key(n)==k);b=blocks[n]
        if b.get('superseded_source_forms') and '[Repealed]' in b['heading']:
            removals.append({'file':slug+'/'+k+'.md','section':n,'official':b})
            del version['units'][k]
    allowed={('-', '–'),('-', '—'),("'",'’'),("'",'‘'),('"','“'),('"','”')}
    for k,u in version['units'].items():
        n=next(n for n in blocks if unit_key(n)==k);b=blocks[n]
        assert not re.search(r'\[(?:Effective|Repealed|Contingently)',b['heading'],re.I),n
        before=u['text'];assert (r/slug/(k+'.md')).read_text(encoding='utf8')==before
        after=before;subs=[]
        if output_text(before)!=b['text']:
            assert '<table' not in before,k
            pos=[p for p in range(2 if before.startswith('# ') else 0,len(before)) if not before[p].isspace()]
            target=[c for c in b['text'] if not c.isspace()];assert len(pos)==len(target),(k,'word/content disagreement')
            chars=list(before)
            for at,c in enumerate(target):
                x=chars[pos[at]]
                if x!=c:
                    assert (x,c) in allowed,(k,'non-punctuation disagreement',x,c)
                    subs.append({'at':at,'published':x,'official':c});chars[pos[at]]=c
            after=''.join(chars);assert output_text(after)==b['text'],k
            changes.append(k);edits.append({'file':slug+'/'+k+'.md','edits':subs});u['text']=after
        proof.append({'file':slug+'/'+k+'.md','url':b['url'],'official_sha256':hashlib.sha256(b['text'].encode()).hexdigest(),
                      'exact_match':output_text(after)==b['text']})
    omitted=[{'section':n,**b} for n,b in blocks.items() if unit_key(n) not in version['units']]
    assert all(noncurrent_notice(b) for b in omitted),omitted
    latest=[d for d in dates if d['day']==day]
    assert latest
    basis=f'Latest effective date printed across all {len(rows)-1} official Title {int(title)} chapters: '+latest[0]['context']
    supersedes=git(job,'log','--format=%H','--diff-filter=A','--',slug+'/'+next(iter(version['units']))+'.md').splitlines()[-1]
    version['from']=day
    version['correction']={'reason':f'reconcile Title {int(title)} source date and official punctuation',
                           'in_force_basis':basis,'text_as_of':old,'supersedes':supersedes}
    version['source_images']=0
    source_hash=hashlib.sha256()
    for row in rows[1:]:source_hash.update(row['url'].encode()+bytes.fromhex(row['sha256']))
    version['sha256']=source_hash.hexdigest()
    assert build.validate(corpus)==[]
    raw=(json.dumps(corpus,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n').encode('utf8')
    (i/'corpus.json').write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
    save(e/f'source-gate-{title}.json',{'pages':rows[1:],'proof':proof,'changes':edits,'source_sections':len(blocks),
         'excluded_noncurrent':omitted,'latest_date':day,'latest_evidence':latest,'dates':dates,'recent_notes':notes,
         'removed_repealed_units':removals,'images':{'source':0,'referenced':0,'omitted':0},'comparison':'official HTML via independent lxml and BeautifulSoup parsers against unchanged published files; punctuation from source only'})
    files=sorted([slug+'/'+k+'.md' for k in version['units']]+[x['file'] for x in removals])
    for k in changes:(r/slug/(k+'.md')).write_text(version['units'][k]['text'],encoding='utf8',newline='\n')
    for x in removals:(r/x['file']).unlink()
    for start,end in ((day,'2026-11-01'),(old,'')):
        message=(f'Correction: {int(title)} V.S.A., source-dated current text\n\n'
          f'All {len(proof)} retained sections checked against the official HTML; source punctuation restored.\n\n'
          f'Kind: correction\nIn-force: {day}\nCorrects: {slug} {start}..{end}\nSupersedes: {supersedes}\n'
          f'Reason: reconcile current-title source date, printed repeal and official punctuation\nAct-path: {slug}\n'+
          ''.join('Files: '+p+'\n' for p in files)+f'Source: https://legislature.vermont.gov/statutes/title/{title}\n'+
          ''.join('Text-source: '+u+'\n' for u in sorted(set(d['url'] for d in latest)))+
          f'Corpus-standard: 1\nText-as-of: {old}\nIn-force-basis: {basis}\n')
        msg=i/f'correction-{title}-{start}.txt';msg.write_text(message,encoding='utf8')
        if start==day:
            if changes or removals:git(job,'add','--',*sorted([slug+'/'+k+'.md' for k in changes]+[x['file'] for x in removals]))
        else:
            p=r/slug/'README.md';s=p.read_text(encoding='utf8');needle=f'from {old} (latest in force: {old})'
            assert needle in s;p.write_text(s.replace(needle,f'from {day} (latest in force: {day})'),encoding='utf8',newline='\n')
            git(job,'add','--',slug+'/README.md')
        if not (intermediate and start==old):
            git(job,'-c','gc.auto=0','commit','--allow-empty','--no-gpg-sign','-F',str(msg))
            print('STREAM',slug,start,git(job,'rev-parse','HEAD'),flush=True)
    metadata=json.loads((r/'data/versions.json').read_text(encoding='utf8'))
    mv=next(a for a in metadata['acts'] if a['slug']==slug)['versions'][0];assert mv['from']==old;mv['from']=day
    mv['sha256']=version['sha256'];mv['source_images']=0
    mv['units']=len(version['units'])
    save(r/'data/versions.json',metadata);(r/'data/corpus.sha256').write_text(sha+'  corpus.json\n',encoding='utf8')
    p=r/'data/commits.csv';p.write_text(p.read_text(encoding='utf8')+f'{day},correction,,{slug},{len(proof)},main\n'*2,encoding='utf8',newline='\n')
    p=r/'README.md';s=p.read_text(encoding='utf8');needle='- Title 31 current text is dated'
    addition=(f'- Title {int(title)} current text is dated **{dt.date.fromisoformat(day).strftime("%d %B %Y").lstrip("0")}**, the latest effective day printed across its {len(rows)-1} current chapters. All {len(proof)} retained sections match the official text after labelled source punctuation corrections.'+
              (' Section 38 is omitted as repealed on 1 July 2025 by 2019 No. 77, section 25.' if removals else '')+'\n')
    assert needle in s;s=s.replace(needle,addition+needle)
    p.write_text(s,encoding='utf8',newline='\n')
    p=r/'REPRODUCE.md';s=p.read_text(encoding='utf8');lines=s.splitlines()
    lines=[line.replace(old,day) if line.startswith('| `'+slug+'` |') else line for line in lines];s='\n'.join(lines)+'\n'
    commits=int(git(job,'rev-list','--count','HEAD'))+1
    corrections=append.check_corrected(r,corpus,'2026-11-13')['corrections']+(1 if intermediate else 0)
    s=re.sub(r'The repository has \d+ commits',f'The repository has {commits} commits',s)
    s=re.sub(r'\| \d+ \| labelled corrections \|',f'| {corrections} | labelled corrections |',s)
    s=re.sub(r'- Corpus: sha256 `[^`]+` \(\d+ bytes\)\.',f'- Corpus: sha256 `{sha}` ({len(raw)} bytes).',s)
    if not intermediate:
        review=('\nThe Title '+str(int(title))+' current snapshot is source-dated '+
                dt.date.fromisoformat(day).strftime('%d %B %Y').lstrip('0')+'. This uses the latest '
                f'effective day printed across all {len(rows)-1} current chapters. '
                f'All {len(proof)} retained sections agree with the original official HTML, including source punctuation; '
                'all source chapter law text agrees with the earlier official captures. '
                'The source image inventory for this snapshot is explicitly zero. '
                'Other titles and earlier consolidated editions remain under review.\n')
        s=s.replace('## Checks\n','## Checks\n'+review)
    p.write_text(s,encoding='utf8',newline='\n')
    git(job,'add','--','README.md','REPRODUCE.md','data/corpus.sha256','data/versions.json','data/commits.csv')
    if intermediate:msg=i/f'correction-{title}-{old}.txt'
    else:
        msg=i/f'docs-{title}.txt';msg.write_text(f'Record source-dated Title {int(title)}\n\nKind: documentation\n',encoding='utf8')
    git(job,'-c','gc.auto=0','commit','--no-gpg-sign','-F',str(msg))
    gate=append.check_corrected(r,corpus,'2026-11-13')
    assert not any(gate.get(k) for k in ('mismatches','tip_mismatches','trailer_errors','missing_in_force','merges','backwards','future_dated','image_errors')),gate
    audit_result=private.audit_push(r,git(job,'rev-parse','HEAD'),head);assert audit_result==[],audit_result
    assert not git(job,'status','--porcelain')
    save(e/f'batch-{title}.json',{'base':head,'head':git(job,'rev-parse','HEAD'),'units':len(proof),'changed_files':len(changes),'removed_files':[x['file'] for x in removals],
                               'gate':gate,'audit_push':audit_result,'corpus_sha256':sha})
    print('BATCH PASSED',slug,len(proof),'changed',len(changes),flush=True)

def fetch_held26(job):
    """Refresh only the Title 26 chapter pages named in the inherited held inventory."""
    disk(); evidence=job/'source-evidence'; source_input=job/'input'/'inherited-held-title-26.json'
    held=json.loads(source_input.read_text(encoding='utf8'))
    assert held['act']=='title-26'
    # The listing was fetched before any chapter pages. A retry reads its saved
    # scheduler cache entry and reuses every chapter already in the manifest.
    listing=fetch('https://legislature.vermont.gov/statutes',job)
    listing_raw=(evidence/listing['sha256']).read_bytes()
    listed_titles=set(html.fromstring(listing_raw).xpath('//a[starts-with(@href,"/statutes/title/")]/@href'))
    assert len(listed_titles)==46 and '/statutes/title/26' in listed_titles,('official title inventory',len(listed_titles))
    manifest=evidence/'fetched-held-26.json'
    rows=json.loads(manifest.read_text(encoding='utf8')) if manifest.exists() else []
    if rows:
        assert rows[0]['url']=='https://legislature.vermont.gov/statutes/title/26'
        for row in rows:
            raw=(evidence/row['sha256']).read_bytes(); assert hashlib.sha256(raw).hexdigest()==row['sha256']
        title_row=rows[0]
    else:
        title_row=fetch('https://legislature.vermont.gov/statutes/title/26',job,refresh=True)
        rows=[title_row]; save(manifest,rows)
    title_raw=(evidence/title_row['sha256']).read_bytes(); title_tree=html.fromstring(title_raw)
    chapter_paths=set(p.replace('/statutes/chapter/','/statutes/fullchapter/') for p in
                      title_tree.xpath('//a[starts-with(@href,"/statutes/chapter/26/")]/@href'))
    selected=sorted(set(x['url'] for x in held['sections']))
    assert selected and all(url.removeprefix('https://legislature.vermont.gov') in chapter_paths for url in selected),\
        'held chapter URL absent from official Title 26 listing'
    failed=[]
    completed={row['url'] for row in rows[1:]}
    for index,url in enumerate(selected,1):
        if url in completed:
            continue
        try:
            row=fetch(url,job,refresh=True); rows.append(row)
        except ValueError as exc:
            failed.append({'url':url,'reason':str(exc)})
        save(evidence/'fetched-held-26.json',rows)
        print('FETCH HELD 26',index,'/',len(selected),url,flush=True)
    save(evidence/'fetch-held-26-failures.json',failed)
    candidates=[]
    selected_rows={row['url']:row for row in rows[1:]}
    for url in selected[:5]:
        row=selected_rows[url]
        row.update(act='title-26',published=True,disposition='already on supplied published main')
        candidates.append(row)
    save(evidence/'five-candidates.json',candidates)
    save(evidence/'listing.json',{'source':listing,'title_26':title_row,'title_count':len(listed_titles),
         'held_chapter_count':len(selected),'terms_basis':'Published REPRODUCE.md source record dated 2026-10-30: no reuse terms found on statute pages; under 30 days.',
         'published_head':git(job,'rev-parse','HEAD')})
    save(evidence/'host-report.json',fs.host_report('legislature.vermont.gov'))
    if failed: raise RuntimeError(f'held Title 26 source pages unavailable: {failed}')
    print('FETCH HELD 26 COMPLETE',len(selected),'chapters; five source candidates recorded',flush=True)

def audit_held26(job):
    """Compare every inherited Title 26 hold against refreshed official HTML with two DOM parsers."""
    evidence=job/'source-evidence'; rows=json.loads((evidence/'fetched-held-26.json').read_text(encoding='utf8'))
    held=json.loads((job/'input'/'inherited-held-title-26.json').read_text(encoding='utf8'))
    selected={row['url'] for row in rows[1:]}; blocks={}; parser_checks=[]; dates=[]; images=[]
    for row in rows[1:]:
        raw=(evidence/row['sha256']).read_bytes(); assert hashlib.sha256(raw).hexdigest()==row['sha256']
        tree=html.fromstring(raw); bs=BeautifulSoup(raw,'html.parser'); bs_blocks={}
        old=HERE/'.cache'/(hashlib.sha256(row['url'].encode()).hexdigest()+'.bin')
        drift=None
        if old.exists():
            old_raw=old.read_bytes(); oldtree=html.fromstring(old_raw)
            selector='//ul[contains(@class,"statutes-list") or contains(@class,"statutes-detail")]'
            old_text=[source_text(n) for n in oldtree.xpath(selector)]
            new_text=[source_text(n) for n in tree.xpath(selector)]
            if old_text!=new_text:
                drift={'url':row['url'],'old_source_sha256':hashlib.sha256(old_raw).hexdigest(),
                       'fresh_source_sha256':row['sha256'],'old_text_sha256':hashlib.sha256('\n'.join(old_text).encode()).hexdigest(),
                       'fresh_text_sha256':hashlib.sha256('\n'.join(new_text).encode()).hexdigest()}
        for li in bs.select('ul.statutes-list li, ul.statutes-detail li'):
            div=li.find('div',recursive=False)
            if div is None: continue
            p=next((p for p in div.find_all('p') if p.get_text(strip=True)),None)
            if p is None: continue
            n=number(norm(bs_text(p)))
            if n: bs_blocks.setdefault(n,[]).append(norm(bs_text(li)))
        seen=set(); positions={}
        for li in tree.xpath('//ul[contains(@class,"statutes-list") or contains(@class,"statutes-detail")]//li'):
            first=next((p for p in li.xpath('./div//p') if ''.join(p.itertext()).strip()),None)
            if first is None: continue
            n=number(source_text(first))
            if not n: continue
            seen.add(n); text=source_text(li); at=positions.get(n,0); positions[n]=at+1
            assert text==bs_blocks[n][at],('independent DOM parsers differ',row['url'],n)
            blocks.setdefault(n,[]).append({'text':text,'url':row['url'],'heading':source_text(first)})
            for img in li.xpath('.//img|.//svg|.//object|.//embed|.//canvas|.//*[@style and contains(@style,"url(")]'):
                images.append({'section':n,'url':row['url'],'element':img.tag,'image':img.get('src') or img.get('data') or img.get('style')})
            for m in DATE.finditer(text):
                day=dt.date(int(m[3]),MONTHS[m[1].lower()],int(m[2])).isoformat()
                dates.append({'section':n,'day':day,'quote':m.group(),'context':text[max(0,m.start()-150):min(len(text),m.end()+50)],'url':row['url']})
        assert seen==set(bs_blocks) and all(positions[n]==len(bs_blocks[n]) for n in seen),('section sets differ',row['url'])
        if drift: parser_checks.append({'source_capture_drift':drift})
    assert selected=={x['url'] for x in held['sections']}
    repo=repo_path(job); corpus_path=job/'input'/'corpus.json'; corpus=json.loads(corpus_path.read_text(encoding='utf8'))
    assert hashlib.sha256(corpus_path.read_bytes()).hexdigest()==(repo/'data/corpus.sha256').read_text(encoding='utf8').split()[0]
    act=next(a for a in corpus['acts'] if a['slug']=='title-26'); results=[]; unresolved=[]; exact=0
    for item in held['sections']:
        key=Path(item['file']).stem; section=re.sub(r'^sec-0*','',key)
        forms=blocks.get(section,[])
        if len(forms)!=1:
            unresolved.append({'file':item['file'],'reason':f'{len(forms)} source forms in refreshed response; requires date-form selection'})
            continue
        form=forms[0]; version=next((v for v in act['versions'] if v['from']<='2026-11-13'),None)
        unit=(version or {}).get('units',{}).get(key)
        if not unit:
            unresolved.append({'file':item['file'],'reason':'unit absent from current version'})
            continue
        before=unit['text']; source=form['text']; equal=output_text(before)==source
        rec={'file':item['file'],'url':form['url'],'published_text_sha256':hashlib.sha256(before.encode()).hexdigest(),
             'official_text_sha256':hashlib.sha256(source.encode()).hexdigest(),'source_html_sha256':next(r['sha256'] for r in rows if r['url']==form['url']),
             'tables_in_inherited_hold':item['tables'],'source_image_count':sum(1 for x in images if x['section']==section),'exact_match':equal}
        if equal:
            exact+=1; rec['disposition']='fresh official text agrees'; results.append(rec); continue
        if '<table' in before or item['tables']:
            rec['disposition']='held: textual table discrepancy requires table-aware source review'
            unresolved.append({'file':item['file'],'reason':rec['disposition']}); results.append(rec); continue
        version_texts=[v.get('units',{}).get(key,{}).get('text') for v in act['versions']]
        if any(text is None for text in version_texts) or len(set(version_texts))!=1:
            rec['disposition']='held: published versions differ; correction needs dated source-form selection'
            unresolved.append({'file':item['file'],'reason':rec['disposition']}); results.append(rec); continue
        pos=[p for p in range(2 if before.startswith('# ') else 0,len(before)) if not before[p].isspace()]
        target=[c for c in source if not c.isspace()]
        allowed={('-', 'â€“'),('-', 'â€”'),("'",'â€™'),("'",'â€˜'),('"','â€œ'),('"','â€')}
        if len(pos)!=len(target):
            rec['disposition']='held: non-punctuation content length differs'
            unresolved.append({'file':item['file'],'reason':rec['disposition']}); results.append(rec); continue
        changes=[]; chars=list(before); safe=True
        for at,c in enumerate(target):
            old_char=chars[pos[at]]
            if old_char!=c:
                if (old_char,c) not in allowed: safe=False; break
                changes.append({'compact_position':at,'published':old_char,'official':c}); chars[pos[at]]=c
        after=''.join(chars)
        if not safe or output_text(after)!=source:
            rec['disposition']='held: discrepancy is not a proven source punctuation correction'
            unresolved.append({'file':item['file'],'reason':rec['disposition']}); results.append(rec); continue
        rec['disposition']='safe punctuation-only correction'; rec['changes']=changes; rec['corrected_text']=after
        results.append(rec)
    save(evidence/'held-audit-26.json',{'base_head':git(job,'rev-parse','HEAD'),'title_versions':[v['from'] for v in act['versions']],
         'source_rows':rows[1:],'source_text_comparisons':results,'exact_matches':exact,'safe_punctuation':sum(x['disposition']=='safe punctuation-only correction' for x in results),
         'unresolved':unresolved,'independent_parser':'lxml and BeautifulSoup section text matched for every refreshed chapter page',
         'source_capture_drift':parser_checks,'held_section_source_images':images,'date_labels':dates,
         'comparison':'refreshed official HTML response bytes vs unchanged published corpus version effective 2026-11-13'})
    print('HELD26 AUDIT',len(results),'sections; exact',exact,'safe_punctuation',sum(x['disposition']=='safe punctuation-only correction' for x in results),'unresolved',len(unresolved),'images',len(images),flush=True)
    return {'base_head':git(job,'rev-parse','HEAD'),'results':results,'unresolved':unresolved,'dates':dates}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--mode',choices=['fetch','audit','build','run','held26-fetch','held26-audit'],required=True);ap.add_argument('--titles',nargs='+')
    ap.add_argument('--day');ap.add_argument('--baseline',type=Path);ap.add_argument('--intermediate',action='store_true');args=ap.parse_args();job=args.job
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    job.mkdir(exist_ok=True);(job/'source-evidence').mkdir(exist_ok=True)
    with (job/'pids.txt').open('a') as f:f.write(f'{os.getpid()} collect_depth.py {args.mode}\n')
    original_popen=subprocess.Popen
    def tracked_popen(*a,**kw):
        kw['creationflags']=kw.get('creationflags',0)|subprocess.BELOW_NORMAL_PRIORITY_CLASS
        proc=original_popen(*a,**kw)
        with (job/'pids.txt').open('a') as f:f.write(f'{proc.pid} child process\n')
        return proc
    subprocess.Popen=tracked_popen
    disk()
    if args.mode=='held26-fetch':
        fetch_held26(job)
    elif args.mode=='held26-audit':
        audit_held26(job)
    elif args.mode in ('fetch','run'):
        assert args.titles
        robots=fetch('https://legislature.vermont.gov/robots.txt',job)
        listing=fetch('https://legislature.vermont.gov/statutes',job)
        raw=(job/'source-evidence'/listing['sha256']).read_bytes()
        paths=sorted(set(p.split('#')[0] for p in html.fromstring(raw).xpath('//a[starts-with(@href,"/statutes/title/")]/@href')))
        save(job/'source-evidence'/'listing.json',{'source':listing,'robots':robots,'title_count':len(paths),'paths':paths,
             'terms_basis':'Published REPRODUCE.md source record dated 2026-10-30: no reuse terms found on statute pages (under 30 days).',
             'published_head':git(job,'rev-parse','origin/main')})
        batches=[];held=[]
        for title in args.titles:
            try:
                result=fetch_title(job,title)
                if args.mode=='run':
                    assert args.baseline
                    assert not result.get('held'),result.get('held')
                    day=max(d['day'] for d in result['dates'] if d['day']<='2026-11-13')
                    build_title(job,title,day,args.baseline)
                    batches.append({'title':title,'day':day,'head':git(job,'rev-parse','HEAD')})
            except (fs.HostStopped,fs.HostDailyCap,fs.NotNow):raise
            except Exception as exc:
                held.append({'title':title,'reason':str(exc)})
                print('HELD',title,str(exc),flush=True)
                # Never continue after a partially applied batch.
                if git(job,'status','--porcelain'):raise
            save(job/'source-evidence'/'run-batches.json',{'batches':batches,'held':held})
        candidates=[]
        for title,ch in [('25','001'),('22','001'),('29','001'),('31','001'),('04','001')]:
            row=fetch(f'https://legislature.vermont.gov/statutes/fullchapter/{title}/{ch}',job)
            row.update(act='title-'+str(int(title)),published=True,disposition='already on published main')
            assert (job/'published'/row['act']).is_dir();candidates.append(row)
        save(job/'source-evidence'/'five-candidates.json',candidates)
        save(job/'source-evidence'/'host-report.json',fs.host_report('legislature.vermont.gov'))
    elif args.mode=='audit':
        assert args.titles
        for title in args.titles:audit(job,title)
    else:
        assert args.titles
        assert len(args.titles)==1 and args.day and args.baseline
        build_title(job,args.titles[0],args.day,args.baseline,args.intermediate)

if __name__=='__main__':main()
