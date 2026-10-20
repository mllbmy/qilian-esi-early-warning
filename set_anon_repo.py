"""Insert an anonymous mirror URL and rebuild the current local release.

Usage: python set_anon_repo.py https://anonymous.4open.science/r/actual-id
Use --no-build for source only. This does not publish or upload files.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from current_release import PACKAGE as P,ROOT,DELIVERY as OUT,WORK as W,VERSION

PATTERN=re.compile(r'https://anonymous\.4open\.science/r/[A-Za-z0-9._-]+')

def run(args,cwd,env):
    result=subprocess.run([str(a) for a in args],cwd=cwd,env=env,capture_output=True,text=True,
                          encoding='utf-8',errors='replace')
    logs=W/'logs';logs.mkdir(parents=True,exist_ok=True)
    name=Path(str(args[0])).stem+'_'+Path(str(args[-1])).stem
    (logs/('mirror_rebuild_'+re.sub(r'[^A-Za-z0-9_-]','_',name)+'.log')).write_text(
        result.stdout+'\n'+result.stderr,encoding='utf-8')
    if result.returncode:raise SystemExit(result.stdout[-1500:]+result.stderr[-1500:])

def main():
    if len(sys.argv)<2:raise SystemExit(__doc__)
    url=sys.argv[1].strip()
    if not PATTERN.fullmatch(url) or 'REPLACE-WITH-MIRROR-ID' in url or len(url.split('/r/')[-1])<4:
        raise SystemExit('Supply an actual https://anonymous.4open.science/r/<id> URL.')
    tex=P/'manuscript.tex';s=tex.read_text(encoding='utf-8')
    assert PATTERN.search(s),'No anonymous URL in manuscript source'
    tex.write_text(PATTERN.sub(url,s),encoding='utf-8',newline='\n')
    if '--no-build' in sys.argv[2:]:
        print('Updated manuscript source only. Rebuild before submission.');return
    env=os.environ.copy();env['TEXINPUTS']='.;'+P.as_posix()+'/;'
    env['PYTHONPYCACHEPREFIX']=str(W/'cache/pycache')
    (W/'temp').mkdir(parents=True,exist_ok=True);env['TEMP']=env['TMP']=str(W/'temp')
    latex=W/'latex';latex.mkdir(parents=True,exist_ok=True)
    compiler=shutil.which('pdflatex')
    if compiler is None:
        candidate=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/MiKTeX/miktex/bin/x64/pdflatex.exe'
        compiler=str(candidate) if candidate.exists() else None
    if not compiler:raise SystemExit('pdflatex unavailable; source URL updated, release not rebuilt.')
    run([sys.executable,P/'make_bbl_jms.py'],P,env)
    for _ in range(3):run([compiler,'-interaction=nonstopmode','-halt-on-error',tex],latex,env)
    builders=P/'tools/docx_build'
    for name in ['build_docx.py','build_front_matter.py']:run([sys.executable,builders/name],builders,env)
    ps=shutil.which('pwsh') or shutil.which('powershell')
    if not ps:raise SystemExit('Word PDF export requires PowerShell on Windows.')
    run([ps,'-NoProfile','-File',builders/'export_review_pdf.ps1','-Docx',
         OUT/f'论文_EN_{VERSION}版本_投稿用.docx','-OutputPdf',
         OUT/f'论文_EN_{VERSION}版本_校对版.pdf'],ROOT,env)
    run([sys.executable,P/'build_release.py'],P,env)
    print('Rebuilt current release:',OUT)
    print('Remote mirror contents and Zenodo permissions still require author verification.')

if __name__=='__main__':main()
