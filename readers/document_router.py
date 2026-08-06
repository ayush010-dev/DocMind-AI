import os

from readers.pdf_reader import extract_text as pdf_extract
from readers.txt_reader import extract_text as txt_extract
from readers.docx_reader import extract_text as docx_extract
from readers.pptx_reader import extract_text as pptx_extract
from readers.excel_reader import extract_text as excel_extract


def read_document(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return pdf_extract(file_path)

    elif extension == ".txt":
        return txt_extract(file_path)

    elif extension == ".docx":
        return docx_extract(file_path)
    
    elif extension == ".pptx":
        return pptx_extract(file_path)
    
    elif extension == ".xlsx":
        return excel_extract(file_path)

    return "Unsupported File Type"