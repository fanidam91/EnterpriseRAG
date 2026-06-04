import os
import sys

def check_and_install_dependencies():
    print("Checking dependencies for document generation...")
    required_packages = ["reportlab", "python-docx", "openpyxl", "python-pptx"]
    missing = []
    
    # Try importing
    try:
        import reportlab
    except ImportError:
        missing.append("reportlab")
    try:
        import docx
    except ImportError:
        missing.append("python-docx")
    try:
        import openpyxl
    except ImportError:
        missing.append("openpyxl")
    try:
        import pptx
    except ImportError:
        missing.append("python-pptx")
        
    if missing:
        print(f"Missing packages: {missing}. Installing via pip...")
        import subprocess
        try:
            subprocess.run([sys.executable, "-m", "pip", "install"] + required_packages, check=True)
            print("Dependencies installed successfully!")
        except Exception as e:
            print(f"Failed to install dependencies automatically: {e}")
            print("Please run: pip install reportlab python-docx openpyxl python-pptx")
            return False
    return True

def generate_pdf(output_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2563EB'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=10.5,
        textColor=colors.HexColor('#334155'),
        leading=14,
        spaceAfter=10
    )

    # Title
    story.append(Paragraph("Enterprise Global Holdings - HR Employee Handbook 2026", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Document Classification: RESTRICTED - HR ONLY", ParagraphStyle('Sub', parent=body_style, textColor=colors.HexColor('#DC2626'), fontSize=10, bold=True)))
    story.append(Spacer(1, 15))

    # Content
    story.append(Paragraph("Section 1: Annual Leave & Time Off Policy", h2_style))
    story.append(Paragraph(
        "All full-time employees are entitled to 20 days of paid annual leave per calendar year. "
        "Leave accrues monthly at a rate of 1.67 days. Employees must request annual leave through the HR Portal at least 14 days in advance. "
        "A maximum of 5 unused annual leave days can be carried over to the next calendar year, and must be used by March 31st, or they will be forfeited. "
        "Bereavement leave is allocated separately, providing up to 5 days of paid time off for immediate family members.",
        body_style
    ))

    story.append(Paragraph("Section 2: Flexible Hybrid Work Guidelines", h2_style))
    story.append(Paragraph(
        "Our hybrid work model requires employees to spend a minimum of 3 days per week in the local office, with the remaining 2 days eligible for remote work. "
        "Remote work days must be aligned with the team manager to ensure coverage. "
        "Core collaboration hours are between 10:00 AM and 3:00 PM local time. "
        "The company provides a one-time remote home office setup stipend of $500 to purchase ergonomic equipment (e.g., monitor, chair, keyboard).",
        body_style
    ))

    story.append(Paragraph("Section 3: Annual Performance & Review Cycle", h2_style))
    story.append(Paragraph(
        "Performance reviews are conducted twice a year to facilitate growth, alignment, and reward allocation. "
        "The Mid-Year Review takes place during June, focusing on progress against goals and course corrections. "
        "The Year-End Review is conducted in December, leading to performance rating assignments, salary reviews, and discretionary bonus calculations. "
        "Self-evaluations must be completed in the system by the 10th of the review month.",
        body_style
    ))

    doc.build(story)
    print(f"Generated PDF: {output_path}")

def generate_docx(output_path):
    import docx
    from docx.shared import Inches, Pt
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn

    doc = docx.Document()
    
    # Title
    title = doc.add_paragraph()
    run = title.add_run("IT Security Standard Operating Procedures & Incident Plan")
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.name = 'Calibri'
    
    # Subtitle classification
    sub = doc.add_paragraph()
    r = sub.add_run("Document Classification: CONFIDENTIAL - IT/SECURITY ONLY")
    r.bold = True
    r.font.color.rgb = docx.shared.RGBColor(220, 38, 38)
    
    # Headings and Body
    h1 = doc.add_heading(level=1)
    h1_run = h1.add_run("1. Password and Authentication Requirements")
    h1_run.font.color.rgb = docx.shared.RGBColor(37, 99, 235)
    
    p1 = doc.add_paragraph(
        "All corporate passwords must be a minimum of 14 characters in length and include a mix of uppercase letters, lowercase letters, numbers, and special characters. "
        "Passwords must be changed every 365 days. Reusing any of the previous 5 passwords is strictly prohibited. "
        "Multi-Factor Authentication (MFA) is mandatory for all system logins, including VPN, Azure Portal, and SaaS applications. "
        "Single Sign-On (SSO) integration is required for all new software procurements."
    )
    
    h2 = doc.add_heading(level=1)
    h2_run = h2.add_run("2. Phishing and Security Incident Escalation Flow")
    h2_run.font.color.rgb = docx.shared.RGBColor(37, 99, 235)
    
    p2 = doc.add_paragraph(
        "If an employee suspects a phishing attempt, they must click the 'Report Phishing' button in Outlook immediately. "
        "In the event of a verified security breach or malware infection: "
        "1. Disconnect the affected computer from the network (unplug ethernet and disable Wi-Fi). "
        "2. Notify the Security Operations Center (SOC) hotline at ext. 911 or via email at soc@company.com. "
        "3. The Incident Response Team will initiate containment within 15 minutes of logging. "
        "4. A post-incident analysis report must be filed in Unity Catalog under the `it_audit.security_incidents` table within 48 hours."
    )

    doc.save(output_path)
    print(f"Generated DOCX: {output_path}")

def generate_xlsx(output_path):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Q1 Financial Summary"
    
    # Set Gridlines visible
    ws.views.sheetView[0].showGridLines = True

    # Styling
    title_font = Font(name="Calibri", size=16, bold=True, color="1E293B")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=11, color="334155")
    total_font = Font(name="Calibri", size=11, bold=True, color="1E293B")
    
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    total_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    double_bottom_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='double', color='1E293B')
    )

    # Title block
    ws['A1'] = "Enterprise Global Holdings - Q1 Performance Statement"
    ws['A1'].font = title_font
    ws['A2'] = "Classification: CONFIDENTIAL - FINANCE ONLY"
    ws['A2'].font = Font(name="Calibri", size=10, bold=True, color="DC2626")
    
    # Empty space
    ws.append([])
    
    # Headers
    headers = ["Department", "Q1 Target Budget ($)", "Q1 Actual Cost ($)", "Variance ($)", "Efficiency Rating"]
    ws.append(headers)
    
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=4, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        
    # Data
    data = [
        ["Human Resources", 1200000, 1150000, "=B5-C5", "95.8%"],
        ["Finance & Tax", 850000, 890000, "=B6-C6", "104.7%"],
        ["Information Technology", 3400000, 3150000, "=B7-C7", "92.6%"],
        ["Marketing & Sales", 2500000, 2600000, "=B8-C8", "104.0%"],
        ["Operations", 4200000, 4100000, "=B9-C9", "97.6%"]
    ]
    
    for row in data:
        ws.append(row)
        row_idx = ws.max_row
        for col_idx in range(1, len(row) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            if col_idx in [2, 3, 4]:
                cell.number_format = "$#,##0"
                cell.alignment = Alignment(horizontal="right")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="center")
                
    # Total Row
    total_row = ["Total", "=SUM(B5:B9)", "=SUM(C5:C9)", "=B10-C10", "97.7%"]
    ws.append(total_row)
    total_row_idx = ws.max_row
    
    for col_idx in range(1, len(total_row) + 1):
        cell = ws.cell(row=total_row_idx, column=col_idx)
        cell.font = total_font
        cell.fill = total_fill
        cell.border = double_bottom_border
        if col_idx in [2, 3, 4]:
            cell.number_format = "$#,##0"
            cell.alignment = Alignment(horizontal="right")
        elif col_idx == 5:
            cell.alignment = Alignment(horizontal="center")

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or '')
            if val.startswith('='):
                val = "$9,999,999" # Proxy length for formula formatting
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(output_path)
    print(f"Generated XLSX: {output_path}")

def generate_pptx(output_path):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor

    prs = Presentation()
    
    # Slide 1: Title
    slide_layout = prs.slide_layouts[0] # Title slide
    slide = prs.slides.add_slide(slide_layout)
    
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = "Company Operations & Guidelines Playbook"
    subtitle.text = "Operational Excellence Framework & General Policy\nClassification: PUBLIC / GENERAL AUDIENCE"
    
    # Slide 2: Core Values
    slide_layout = prs.slide_layouts[1] # Title and Content
    slide = prs.slides.add_slide(slide_layout)
    
    title = slide.shapes.title
    title.text = "Our Corporate Operations Guidelines"
    
    tf = slide.placeholders[1].text_frame
    tf.text = "1. Customer Obsession"
    
    p = tf.add_paragraph()
    p.text = "   - We start with the customer and work backwards. We work vigorously to earn and keep customer trust."
    p.font.size = Pt(16)
    
    p = tf.add_paragraph()
    p.text = "2. Frugality"
    p.font.bold = True
    
    p = tf.add_paragraph()
    p.text = "   - Accomplish more with less. Constraints breed resourcefulness, self-sufficiency, and invention."
    p.font.size = Pt(16)
    
    p = tf.add_paragraph()
    p.text = "3. Standards of Conduct"
    p.font.bold = True
    
    p = tf.add_paragraph()
    p.text = "   - All employees are expected to maintain professional relationships. Reports of misconduct must be submitted to HR or the anonymous Whistleblower Portal. Investigation timelines adhere to standard 10-day SLAs."
    p.font.size = Pt(16)

    prs.save(output_path)
    print(f"Generated PPTX: {output_path}")

def main():
    # Target directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "data")
    
    os.makedirs(data_dir, exist_ok=True)
    
    if not check_and_install_dependencies():
        print("Dependency installation failed. Exiting document generator.")
        sys.exit(1)
        
    generate_pdf(os.path.join(data_dir, "HR_Employee_Handbook_2026.pdf"))
    generate_docx(os.path.join(data_dir, "IT_Security_Incident_Response_Plan.docx"))
    generate_xlsx(os.path.join(data_dir, "Finance_Q1_Performance_Statement.xlsx"))
    generate_pptx(os.path.join(data_dir, "Company_Operations_Playbook.pptx"))
    print("All sample documents successfully generated in the 'data/' directory!")

if __name__ == "__main__":
    main()
