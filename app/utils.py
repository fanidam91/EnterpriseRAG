import io
import pypdf
import docx
import openpyxl
import pptx
import traceback

def parse_file_bytes_to_chunks(doc_name, file_bytes):
    """
    Parses document byte streams by extension and splits into semantic chunks.
    Supports PDF, DOCX, XLSX, PPTX, and TXT fallback.
    Returns: List of dicts, each with keys ['section', 'content']
    """
    ext = doc_name.split('.')[-1].lower()
    chunks = []
    
    try:
        if ext == 'pdf':
            chunks = parse_pdf(file_bytes)
        elif ext == 'docx':
            chunks = parse_docx(file_bytes)
        elif ext == 'xlsx':
            chunks = parse_xlsx(file_bytes)
        elif ext == 'pptx':
            chunks = parse_pptx(file_bytes)
        else:
            # Fallback for plain text or unknown
            text = file_bytes.decode('utf-8', errors='ignore')
            chunks = chunk_text(text, "General Text Content")
    except Exception as e:
        print(f"Error parsing document {doc_name}: {e}")
        traceback.print_exc()
        # Create a simple error fallback chunk so the pipeline doesn't break
        chunks = [{"section": "Error Fallback", "content": f"Failed to parse content. Error details: {str(e)}"}]
        
    return chunks

def chunk_text(text, section_name, max_chunk_size=800, overlap=100):
    """
    Splits text into chunks of specified maximum character size with a sliding window overlap.
    """
    chunks = []
    text = text.strip()
    if not text:
        return []
        
    if len(text) <= max_chunk_size:
        return [{"section": section_name, "content": text}]
        
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        
        # Try to find a natural boundary (period, paragraph, newline) within the last 15% of the chunk size
        if end < len(text):
            boundary = text.rfind('. ', end - 120, end)
            if boundary != -1:
                end = boundary + 1
            else:
                newline = text.rfind('\n', end - 80, end)
                if newline != -1:
                    end = newline + 1
                    
        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append({
                "section": section_name,
                "content": chunk_content
            })
            
        start = end - overlap
        if start >= len(text) or (end >= len(text)):
            break
            
    return chunks

def parse_pdf(file_bytes):
    """Parses PDF bytes to chunks page by page."""
    chunks = []
    pdf_file = io.BytesIO(file_bytes)
    reader = pypdf.PdfReader(pdf_file)
    
    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            page_chunks = chunk_text(text, f"Page {page_num}")
            chunks.extend(page_chunks)
            
    return chunks

def parse_docx(file_bytes):
    """Parses Word document bytes to chunks, splitting by headings and paragraphs."""
    chunks = []
    docx_file = io.BytesIO(file_bytes)
    doc = docx.Document(docx_file)
    
    current_section = "Introduction"
    current_text = []
    
    for para in doc.paragraphs:
        # Check if heading
        if para.style.name.startswith('Heading'):
            # Save preceding section first
            if current_text:
                full_text = "\n".join(current_text)
                chunks.extend(chunk_text(full_text, current_section))
                current_text = []
            current_section = para.text.strip()
        else:
            if para.text.strip():
                current_text.append(para.text.strip())
                
    # Ingest remaining text
    if current_text:
        full_text = "\n".join(current_text)
        chunks.extend(chunk_text(full_text, current_section))
        
    return chunks

def parse_xlsx(file_bytes):
    """Parses Excel spreadsheets, creating chunks representing tables or sheets."""
    chunks = []
    xlsx_file = io.BytesIO(file_bytes)
    wb = openpyxl.load_workbook(xlsx_file, data_only=True)
    
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        sheet_lines = []
        
        # Read sheet rows
        for row in sheet.iter_rows(values_only=True):
            # Convert row to string representation
            row_vals = [str(cell) if cell is not None else "" for cell in row]
            if any(row_vals):  # Skip empty rows
                sheet_lines.append(" | ".join(row_vals))
                
        if sheet_lines:
            sheet_text = f"Sheet: {sheet_name}\n" + "\n".join(sheet_lines)
            # Excel chunks might be denser; use slightly larger size limit
            chunks.extend(chunk_text(sheet_text, f"Sheet {sheet_name}", max_chunk_size=1200, overlap=150))
            
    return chunks

def parse_pptx(file_bytes):
    """Parses PowerPoint slide decks, grouping content by slide."""
    chunks = []
    pptx_file = io.BytesIO(file_bytes)
    prs = pptx.Presentation(pptx_file)
    
    for idx, slide in enumerate(prs.slides, 1):
        slide_title = f"Slide {idx}"
        slide_texts = []
        
        # Extract title if present
        if slide.shapes.title:
            slide_title = f"Slide {idx}: {slide.shapes.title.text.strip()}"
            
        # Extract slide shapes text
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    if paragraph.text.strip():
                        slide_texts.append(paragraph.text.strip())
                        
        if slide_texts:
            slide_content = "\n".join(slide_texts)
            chunks.extend(chunk_text(slide_content, slide_title))
            
    return chunks
