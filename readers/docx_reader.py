from docx import Document


def extract_text(file_path):
    """
    Extracts text from DOCX paragraphs, headings, and embedded tables.
    Preserves section structure.
    """
    doc = Document(file_path)
    blocks = []
    current_section = "Document Start"
    current_text = ""

    # Process paragraphs
    for para in doc.paragraphs:
        if para.style and para.style.name.startswith("Heading"):
            if current_text.strip():
                blocks.append({
                    "text": current_text.strip(),
                    "section": current_section
                })
            current_section = para.text.strip()
            current_text = current_section + "\n"
        else:
            if para.text.strip():
                current_text += para.text + "\n"

    # Process tables in DOCX
    table_text = ""
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                table_text += " | ".join(row_cells) + "\n"

    if table_text.strip():
        current_text += "\nTables:\n" + table_text.strip()

    if current_text.strip():
        blocks.append({
            "text": current_text.strip(),
            "section": current_section
        })

    return blocks