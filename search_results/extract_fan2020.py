import fitz
import os

pdf_path = r'G:\minimax - workspace\Paper agent\search_results\pdfs\10_1038_s41579-020-0433-9.pdf'
out_dir = r'G:\minimax - workspace\Paper agent\search_results'

doc = fitz.open(pdf_path)
print(f'Pages: {len(doc)}')
print(f'Title: {doc.metadata.get("title", "")}')
print(f'Author: {doc.metadata.get("author", "")}')

# 全文合并版本
all_text = []
for i in range(len(doc)):
    page = doc[i]
    text = page.get_text('text')
    all_text.append(f'\n========== PAGE {i+1} ==========\n{text}')

combined_path = os.path.join(out_dir, 'fan2020_full.txt')
with open(combined_path, 'w', encoding='utf-8') as f:
    f.write(''.join(all_text))
print(f'Wrote combined: {combined_path}')

# 单独页面
for i, t in enumerate(all_text):
    p = os.path.join(out_dir, f'fan2020_p{i+1:02d}.txt')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(t)
print('Wrote per-page files')
