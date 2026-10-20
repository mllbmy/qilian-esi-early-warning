"""Current local submission build configuration."""
from pathlib import Path
import os

PACKAGE=Path(__file__).resolve().parent
ROOT=PACKAGE.parent
VERSION=os.environ.get('QILIAN_VERSION','2.2')
DELIVERY=ROOT/'交付'/f'{VERSION}版本'
WORK=Path(os.environ.get('QILIAN_WORK',ROOT/'ChatGPT/revision_2.2_2026-10-20'))

