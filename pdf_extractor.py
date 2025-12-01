import PyPDF2
import pdfplumber
import sys
from pathlib import Path

def extract_text_from_pdf(pdf_path, use_pdfplumber=True):
   
    try:
        if use_pdfplumber:
            # Use pdfplumber 
            print("Using pdfplumber for text extraction...")
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = len(pdf.pages)
                print(f"Number of pages in PDF: {num_pages}")
                
                all_text = ""
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text:
                        all_text += f"\n--- Page {page_num} ---\n"
                        all_text += text
                
                return all_text
        else:
            # Fallback to PyPDF2
            print("Using PyPDF2 for text extraction...")
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                print(f"Number of pages in PDF: {num_pages}")
                
                all_text = ""
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    all_text += f"\n--- Page {page_num + 1} ---\n"
                    all_text += text
                
                return all_text
    
    except FileNotFoundError:
        return f"Error: File '{pdf_path}' not found!"
    except ImportError as e:
        if "pdfplumber" in str(e):
            print("\nWarning: pdfplumber not installed. Falling back to PyPDF2...")
            print("For better Sinhala text support, install pdfplumber:")
            print("  pip install pdfplumber")
            return extract_text_from_pdf(pdf_path, use_pdfplumber=False)
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


def display_text(text, max_chars=500):
    """
    Display extracted text with proper Sinhala encoding
    
    Args:
        text: Text content to display
        max_chars: Maximum characters to show in preview
    """
    print("\n=== Extracted Text (Preview) ===")
    print(text[:max_chars], flush=True)
    print("...\n")


def save_text_to_file(text, output_path):
   
    try:
        # Ensure proper Unicode encoding
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(text)
        print(f"\n✓ Text saved to '{output_path}' successfully!")
        print(f"✓ File encoding: UTF-8 (Unicode Sinhala + English fully supported)")
        print(f"✓ Open with Notepad++ or VS Code for proper display")
    except Exception as e:
        print(f"Error saving file: {str(e)}")


def main():
    
    
    print("=== PDF Text Extractor (Sinhala Support) ===\n")
    
    # Check if command line argument is provided
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Get user input
        pdf_path = input("Enter the path to PDF file: ").strip()
    
    # Check if file exists
    if not Path(pdf_path).exists():
        print(f"Error: File '{pdf_path}' not found!")
        return
    
    print(f"\nProcessing PDF file: '{pdf_path}'...\n")
    
    # Extract text
    extracted_text = extract_text_from_pdf(pdf_path)
    
    if extracted_text.startswith("Error"):
        print(extracted_text)
        return
    
    # Print to console
    display_text(extracted_text)
    
    # Ask if user wants to save to file
    save_option = input("\nDo you want to save the text to a file? (y/n): ").lower()
    
    if save_option == 'y':
        # Generate output file name
        output_path = Path(pdf_path).stem + "_extracted.txt"
        save_text_to_file(extracted_text, output_path)
    
    print("\nText extraction completed successfully!")


if __name__ == "__main__":
    main()