import pathlib
import subprocess

# These .log files are UTF-16 LE with BOM. Need to read with utf-16, replace, write back.
log_files = [
    'test_output/_diagnose_proxies.log',
    'test_output/_test_pa_fetch_cnki_e2e.log',
    'test_output/_test_pa_fetch_e2e_v3.log',
]

replacements = [
    # Order matters: longer patterns first
    ('mailto:dengn@gmail.com', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:deng.nju@gmail.com', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:dengn@example.com', 'mailto:paper-agent@users.noreply.github.com'),
    ('deng.nju@gmail.com', 'paper-agent@example.com'),
    ('dengn@gmail.com', 'paper-agent@example.com'),
    ('dengn@example.com', 'paper-agent@example.com'),
    ('dengn@qq.com', 'paper-agent@example.com'),
    ('dengn@163.com', 'paper-agent@example.com'),
    ('dengn+research@outlook.com', 'paper-agent+research@example.com'),
    ('dengn@mavis.local', 'paper-agent@mavis.local'),
    # Path patterns in logs
    ('C:\\Users\\DengN\\.paper-agent', '~/.paper-agent'),
    ('C:\\Users\\DengN\\.mavis', '~/.mavis'),
    ('C:\\Users\\DengN\\.minimax', '~/.minimax'),
    ('C:\\Users\\DengN\\', '~/'),
    ('C:/Users/DengN/', '~/'),
    ('DengN', 'paper-agent-author'),
]

for f in log_files:
    p = pathlib.Path(f)
    raw = p.read_bytes()
    # Detect encoding from BOM
    if raw[:2] == b'\xff\xfe':
        encoding = 'utf-16-le'
        text = raw.decode('utf-16-le')
    elif raw[:3] == b'\xef\xbb\xbf':
        encoding = 'utf-8-sig'
        text = raw[3:].decode('utf-8')
    elif raw[:2] == b'\xfe\xff':
        encoding = 'utf-16-be'
        text = raw.decode('utf-16-be')
    else:
        encoding = 'utf-8'
        text = raw.decode('utf-8', errors='replace')

    original = text
    file_changes = 0
    for old, new in replacements:
        if old in text:
            count = text.count(old)
            text = text.replace(old, new)
            file_changes += count

    if text != original:
        # Re-encode with same encoding
        if encoding == 'utf-16-le':
            p.write_bytes(b'\xff\xfe' + text.encode('utf-16-le'))
        elif encoding == 'utf-8-sig':
            p.write_bytes(b'\xef\xbb\xbf' + text.encode('utf-8'))
        elif encoding == 'utf-16-be':
            p.write_bytes(b'\xfe\xff' + text.encode('utf-16-be'))
        else:
            p.write_text(text, encoding='utf-8')
        print(f'{f}: {file_changes} changes ({encoding})')
    else:
        print(f'{f}: 0 changes (encoding: {encoding})')
