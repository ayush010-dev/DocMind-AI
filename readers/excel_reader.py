from openpyxl import load_workbook

def extract_text(file_path):

    workbook = load_workbook(file_path)

    text = ""

    for sheet in workbook.worksheets:

        text += f"Sheet: {sheet.title}\n"

        for row in sheet.iter_rows(values_only=True):

            row_text = " ".join(
                str(cell) for cell in row if cell is not None
            )

            text += row_text + "\n"

    return text