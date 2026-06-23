"""Debug helper to inspect PDFParser outputs for the sample PDF."""
from poc.detector.pdf_parser import PDFParser
from poc.tests.test_pdf_parser import create_sample_pdf_bytes


def main():
    pdf_bytes = create_sample_pdf_bytes()
    parser = PDFParser()
    out = parser.parse(pdf_bytes)
    print('METADATA:', out.get('metadata'))
    pages = out.get('pages', [])
    for p in pages:
        print('PAGE', p['page_number'])
        spans = p.get('spans') or []
        print('SPANS COUNT', len(spans))
        for s in spans:
            print(s)
    # Inspect rawdict to find text outside page
    import fitz
    doc = fitz.open(stream=create_sample_pdf_bytes(), filetype="pdf")
    page = doc[0]
    rd = page.get_text("rawdict")
    print('\nRAWDICT CONTAINS outside?', 'outside' in str(rd))


if __name__ == '__main__':
    main()
