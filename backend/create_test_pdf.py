from fpdf import FPDF
import os

def create_test_pdf():
    # Get the directory of this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(base_dir, "test_resume.txt")
    pdf_path = os.path.join(base_dir, "test_resume.pdf")

    # Create PDF object
    pdf = FPDF()
    pdf.add_page()
    
    # Set font
    pdf.set_font("Arial", size=12)
    
    # Read the text file
    with open(txt_path, "r") as file:
        lines = file.readlines()
    
    # Add content to PDF
    for line in lines:
        # Remove trailing whitespace and newlines
        line = line.strip()
        if line:
            pdf.cell(200, 10, txt=line, ln=True)
    
    # Save the PDF
    pdf.output(pdf_path)
    print(f"Created {pdf_path}")

if __name__ == "__main__":
    create_test_pdf() 