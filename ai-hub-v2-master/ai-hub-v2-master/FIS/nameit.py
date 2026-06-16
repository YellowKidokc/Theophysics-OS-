"""nameit.py — Quick file namer. Point it at any file, get name suggestions.

Usage:
    python nameit.py <filepath>
    python nameit.py "C:\Users\lowes\Desktop\some_file.docx"
"""

import re, sys, os
from pathlib import Path
from datetime import datetime
from collections import Counter

def extract_text(filepath, max_chars=5000):
    ext = Path(filepath).suffix.lower()
    try:
        if ext in {'.txt','.md','.py','.js','.ts','.jsx','.tsx','.css','.html',
                   '.json','.yaml','.yml','.xml','.csv','.bat','.sh','.ps1',
                   '.sql','.rs','.go','.lean','.toml','.cfg','.ini','.log'}:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()[:max_chars]
    except: pass
    return ''

def get_keywords(text, top_n=6):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stops = {'the','and','for','that','this','with','are','was','from','have',
             'has','not','but','can','will','been','which','their','would',
             'there','what','about','when','make','than','them','into','could',
             'other','more','also','its','over','such','only','some','very',
             'just','div','span','class','style','color','font','margin',
             'padding','background','display','width','height','border',
             'text','size','content','function','return','const','var','let',
             'import','export','none','true','false','null','linear','rgba',
             'solid','center','flex','grid','auto','repeat','align','items'}
    freq = Counter(w for w in words if w not in stops and len(w) > 3)
    return [w for w, _ in freq.most_common(top_n)]

def slugify(words):
    return '-'.join(w.lower() for w in words[:4])

def nameit(filepath):
    path = Path(filepath)
    ext = path.suffix.lower()
    stem = path.stem
    text = extract_text(filepath)
    
    # Get title from HTML if available
    title_match = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ''
    
    # Keywords from content
    keywords = get_keywords(text)
    
    # Use title words if available, else keywords
    if title:
        title_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', title) 
                       if w.lower() not in {'the','and','for','with'}]
        slug = slugify(title_words) if title_words else slugify(keywords)
    else:
        slug = slugify(keywords)
    
    # Baseline clean
    clean = re.sub(r'([a-z])([A-Z])', r'\1-\2', stem)
    clean = re.sub(r'[_\s.]+', '-', clean)
    clean = re.sub(r'[^a-zA-Z0-9\-]', '', clean)
    clean = re.sub(r'-+', '-', clean).strip('-').lower()
    
    date = datetime.now().strftime('%Y%m%d')
    seq = '0001'
    
    print(f"\n  File:     {path.name}")
    print(f"  Size:     {path.stat().st_size:,} bytes")
    if title:
        print(f"  Title:    {title}")
    print(f"  Keywords: {', '.join(keywords)}")
    print(f"\n  ── NAME SUGGESTIONS ──")
    print(f"  baseline:         {clean}{ext}")
    print(f"  domain first:     tp_{slug}_{seq}{ext}")
    print(f"  date first:       {date}_{slug}_tp{ext}")
    print(f"  research:         tp_{slug}_v01_{date}{ext}")
    print(f"  minimal:          {slug}{ext}")
    print(f"  master equation:  E__{slug.upper().replace('-','_')}__W__{date}__TP{ext}")
    print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("  Usage:")
        print("    python nameit.py <file>           — name one file")
        print("    python nameit.py <folder>          — name all files in folder")
        print("    python nameit.py <folder> --deep    — include subfolders")
        sys.exit(1)
    
    target = sys.argv[1]
    deep = '--deep' in sys.argv
    
    if os.path.isfile(target):
        nameit(target)
    elif os.path.isdir(target):
        files = []
        if deep:
            for dirpath, _, filenames in os.walk(target):
                for f in filenames:
                    if not f.startswith('.'):
                        files.append(os.path.join(dirpath, f))
        else:
            files = [os.path.join(target, f) for f in os.listdir(target) 
                     if os.path.isfile(os.path.join(target, f)) and not f.startswith('.')]
        
        print(f"\n  Scanning {len(files)} files in {target}")
        print(f"  {'='*70}")
        for fp in sorted(files):
            nameit(fp)
        print(f"  {'='*70}")
        print(f"  {len(files)} files named.\n")
    else:
        print(f"  Not found: {target}")
