import fitz
from ai.ocr_extractor import extract_text_from_multiple_images

def extract_text(pdf_path):
    """
    Extracts text from PDF pages. Automatically triggers visual OCR fallback
    for scanned pages, images, or low-density text pages.
    Batches images into a minimal number of API calls to bypass rate limits and speed up extraction.
    """
    doc = fitz.open(pdf_path)
    
    blocks = []
    pages_needing_ocr = [] # stores tuples of (page_index, img_bytes)
    
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        
        needs_ocr = False
        if len(text) < 40:
            needs_ocr = True
        else:
            try:
                tables = page.find_tables()
                if tables and len(tables.tables) > 0:
                    needs_ocr = True
            except:
                pass
                
            # If the text has very few spaces compared to newlines (indicative of bad table extraction)
            if not needs_ocr and text.count('\n') > text.count(' ') * 2:
                needs_ocr = True

        if needs_ocr:
            try:
                pix = page.get_pixmap(dpi=250)
                img_bytes = pix.tobytes("png")
                pages_needing_ocr.append((i, img_bytes))
                
                # Placeholder block, will fill OCR text later
                blocks.append({
                    "text": text,
                    "page": i + 1,
                    "extraction_method": "parser", # defaults to parser
                    "_needs_ocr": True
                })
            except Exception as e:
                print(f"[PDF Reader Warning] Failed to get image for page {i + 1}: {e}")
                if text.strip():
                    blocks.append({
                        "text": text,
                        "page": i + 1,
                        "extraction_method": "parser"
                    })
        else:
            blocks.append({
                "text": text,
                "page": i + 1,
                "extraction_method": "parser"
            })
            
    doc.close()

    # Process OCR in smaller batches (e.g., 4 pages) to avoid large payload errors or timeouts
    BATCH_SIZE = 4
    for batch_start in range(0, len(pages_needing_ocr), BATCH_SIZE):
        batch = pages_needing_ocr[batch_start:batch_start + BATCH_SIZE]
        image_bytes_list = [img for _, img in batch]
        
        try:
            extracted_texts = extract_text_from_multiple_images(image_bytes_list, "image/png")
            # Map back to blocks
            for (page_index, _), ocr_text in zip(batch, extracted_texts):
                block = blocks[page_index]
                # Prefer OCR text over the potentially broken parser text
                final_text = ocr_text.strip() if ocr_text.strip() else block["text"]
                if final_text:
                    block["text"] = final_text
                    block["extraction_method"] = "ocr" if ocr_text.strip() else "parser"
        except Exception as e:
            err_msg = str(e)
            if "INVALID_API_KEY" in err_msg or "AI_SERVICE_BUSY" in err_msg:
                raise
            failed_pages = [page_index + 1 for page_index, _ in batch]
            print(f"[PDF Reader Warning] OCR batch fallback failed for pages {failed_pages}: {e}")

    # Clean up blocks and remove placeholders that ended up empty
    final_blocks = []
    for b in blocks:
        if "_needs_ocr" in b:
            del b["_needs_ocr"]
        if b.get("text", "").strip():
            final_blocks.append(b)
            
    return final_blocks