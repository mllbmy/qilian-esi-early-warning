"""Package current local artifacts, figure masters and anonymous reproduction files."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from current_release import PACKAGE as P,ROOT,DELIVERY as OUT,WORK as W,VERSION

FIGS=['fig1_study_area','fig_dpsir_framework','fig_indicator_trends',
      'fig3_esi_timeseries','fig_weights','fig4_alpha_sensitivity',
      'fig_spatial_maps','fig_geodetector_q','fig_interaction','fig_obstacle','fig_annual_validation']

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'图件').mkdir(exist_ok=True)
    for n,name in enumerate(FIGS,1):
        shutil.copyfile(P/'figures'/(name+'.pdf'),OUT/'图件'/f'Figure_{n}.pdf')
    shutil.copyfile(P/'figures/JMS_figure_audit.tsv',OUT/'图件/JMS_figure_audit.tsv')
    # Manuscript deliverables are Word-only; figure PDFs remain vector sources.
    files=[]
    files+=list(P.glob('*.py'))
    # Case-insensitive identity screen. An earlier release shipped verify_v8.py,
    # which mentions the public repository URL and therefore the GitHub account
    # name, because this filter compared against a case-sensitive literal.
    # Tokens live in the private, git-ignored _identity_needles.txt plus generic
    # patterns, so this script itself carries no identity and can ship in the package.
    def _needles():
        # written as concatenations so that this script does not match its own screen
        toks=['git'+'hub.com','orcid'+'.org']
        f=P/'_identity_needles.txt'
        if f.exists():
            toks+=[ln.strip().lower() for ln in f.read_text(encoding='utf-8').splitlines()
                   if ln.strip() and not ln.startswith('#')]
        return tuple(dict.fromkeys(toks))
    BANNED=_needles()
    def scrubbed(f):
        if f.name=='author_local.py' or f.name.startswith('build_word'):
            return False
        low=f.read_text(encoding='utf-8',errors='replace').lower()
        return not any(b in low for b in BANNED)
    files=[f for f in files if scrubbed(f)]
    files += [P/n for n in ['manuscript.tex','manuscript.bib','manuscript.bbl','README.md','README_county_esi.md','LICENSE']]
    files+=list((P/'data').glob('*.csv'))+list((P/'data').glob('*.json'))+list((P/'data').glob('*.geojson'))
    files+=list((P/'data').glob('*.npy'))+list((P/'data').glob('*.npz'))
    files+=list((P/'eco_security').glob('*.py'))
    files+=[P/'figures'/(f+'.pdf') for f in FIGS]+[P/'figures/JMS_figure_audit.tsv']
    files += [P/'tools/docx_build'/f for f in ['build_docx.py','build_front_matter.py','docxbuild_lib.py','omml.py','pdf_support.py','export_review_pdf.ps1']]
    prefix=f'qilian_reproduction_{VERSION}/';manifest={}
    dest=OUT/f'匿名复现包_{VERSION}.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(set(files)):
            data=f.read_bytes();rel=f.relative_to(P).as_posix()
            z.writestr(prefix+rel,data)
            manifest[rel]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
        z.writestr(prefix+'SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    # Inspection covers file contents, not just the archive path names.
    try:
        import author_local as author
        needles=[getattr(author,k,'') for k in ['AUTHOR_EN_DISPLAY','EMAIL','ORCID','AFFIL_EN']]
    except ImportError:
        needles=[]  # Private author metadata is intentionally absent in review ZIPs.
    leaks=[]
    with zipfile.ZipFile(dest) as z:
        for name in z.namelist():
            if name.endswith(('.py','.md','.tex','.bib','.bbl','.csv','.json','.geojson','.txt')):
                low=z.read(name).decode('utf-8',errors='replace').lower()
                if any(n and n.lower() in low for n in needles):leaks.append(name)
                if any(b in low for b in BANNED):leaks.append(name+' (case-insensitive screen)')
    assert not leaks,('identity in reproduction package',leaks)
    refresh_manifest()
    print(json.dumps({'package_files':len(manifest),'identity_leaks':len(leaks),
        'zip_bytes':dest.stat().st_size,'output':str(OUT)},ensure_ascii=False))

def refresh_manifest():
    rows=[]
    for f in sorted(OUT.rglob('*')):
        if f.is_file() and not f.name.startswith('md5清单'):
            rows.append(f'{hashlib.md5(f.read_bytes()).hexdigest().upper()}  {f.stat().st_size:9d}  {f.relative_to(OUT).as_posix()}')
    (OUT/f'md5清单_{VERSION}版本.txt').write_text('# MD5  bytes  file (manifest excluded)\n\n'+'\n'.join(rows)+'\n',encoding='utf-8')

if __name__=='__main__':main()
