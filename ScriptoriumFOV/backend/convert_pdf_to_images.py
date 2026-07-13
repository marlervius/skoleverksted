import fitz  # PyMuPDF
doc = fitz.open('test_output.pdf')
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=150)
    pix.save(f'page_{i+1}.png')
    print(f'Saved page_{i+1}.png')
doc.close()
print('Done!')
