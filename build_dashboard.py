"""Build a self-contained browser demo from a completed pipeline run."""
import json
from pathlib import Path
from pipeline import ROOT, run

def main():
    folder, results = run(ROOT/'data/raw', ROOT/'output')
    template = (ROOT/'dashboard/template.html').read_text()
    # Prevent source text from escaping the embedded JSON script element.
    payload = json.dumps(results).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    (ROOT/'index.html').write_text(template.replace('__REPORT_DATA__', payload))
    print('Built index.html from', folder)

if __name__ == '__main__': main()
