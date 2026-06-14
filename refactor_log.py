import os
from pathlib import Path
from core.logger import logger

def process_file(p):
    content = p.read_text(encoding='utf-8')
    if 'print(' not in content: return
    lines = content.split('\n')
    needs_import = True
    if 'from core.logger import logger' in content:
        needs_import = False
    
    modified = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('print('):
            modified = True
            lower = line.lower()
            if 'error' in lower or 'fail' in lower:
                line = line.replace('print(', 'logger.error(')
            elif 'warn' in lower:
                line = line.replace('print(', 'logger.warning(')
            else:
                line = line.replace('print(', 'logger.info(')
        new_lines.append(line)
    
    if not modified: return
    
    if needs_import:
        insert_idx = 0
        in_doc = False
        for i, l in enumerate(new_lines):
            if l.startswith('"""'):
                in_doc = not in_doc
                continue
            if not in_doc and (l.startswith('import') or l.startswith('from ')):
                insert_idx = i
                break
        new_lines.insert(insert_idx, 'from core.logger import logger')
        
    p.write_text('\n'.join(new_lines), encoding='utf-8')
    logger.info(f'Updated {p}')

for root, dirs, files in os.walk(str(Path(__file__).parent.resolve())):
    if '__pycache__' in root or '.git' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            try:
                process_file(Path(root) / f)
            except Exception as e:
                logger.error(f"Error processing {f}: {e}")
