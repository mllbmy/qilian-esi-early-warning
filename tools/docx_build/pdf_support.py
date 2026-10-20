"""PDF raster support, run with the project's PyMuPDF-capable interpreter."""
from pathlib import Path
import sys
import json
import pymupdf

src,dst,dpi=sys.argv[1],sys.argv[2],int(sys.argv[3])
Path(dst).parent.mkdir(parents=True,exist_ok=True)
with pymupdf.open(src) as d:
    d[0].get_pixmap(matrix=pymupdf.Matrix(dpi/72,dpi/72)).save(dst)
    print(json.dumps({'width':d[0].rect.width,'height':d[0].rect.height}))
