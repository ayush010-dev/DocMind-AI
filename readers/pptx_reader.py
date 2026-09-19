from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from ai.ocr_extractor import extract_text_from_image_bytes


def extract_shape_text(shape):
    """
    Recursively extracts text from PPTX shapes, text frames, tables, and group shapes.
    """
    text = ""
    if hasattr(shape, "text") and shape.text:
        text += shape.text + "\n"

    if shape.has_table:
        for row in shape.table.rows:
            row_str = " ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_str:
                text += row_str + "\n"

    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for sub_shape in shape.shapes:
            text += extract_shape_text(sub_shape)

    return text


def extract_text(file_path):
    """
    Extracts text from PPTX slides, text shapes, tables, and image shapes.
    Triggers visual OCR on embedded pictures if text density is low.
    """
    presentation = Presentation(file_path)
    blocks = []

    for i, slide in enumerate(presentation.slides):
        slide_text = ""
        image_blobs = []

        for shape in slide.shapes:
            slide_text += extract_shape_text(shape)

            # Check if shape is a picture/image
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE or hasattr(shape, "image"):
                try:
                    blob = shape.image.blob
                    content_type = getattr(shape.image, "content_type", "image/png")
                    image_blobs.append((blob, content_type))
                except Exception:
                    pass

        slide_text = slide_text.strip()
        extraction_method = "parser"

        # If text is empty/short or images exist on slide, trigger visual OCR on images
        if len(slide_text) < 40 or image_blobs:
            for blob, content_type in image_blobs:
                try:
                    ocr_result = extract_text_from_image_bytes(blob, mime_type=content_type)
                    if ocr_result:
                        slide_text = (slide_text + "\n" + ocr_result).strip() if slide_text else ocr_result
                        extraction_method = "ocr"
                except Exception as e:
                    print(f"[PPTX Reader Warning] Image OCR failed for slide {i + 1}: {e}")

        if slide_text.strip():
            blocks.append({
                "text": slide_text,
                "slide": i + 1,
                "extraction_method": extraction_method
            })

    return blocks