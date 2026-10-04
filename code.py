from pypdf import PdfReader, PdfWriter

# Input PDF
pdf_path = r"C:\Users\rutik\Downloads\SQL+Notes (1).pdf"

# Pages you want to extract (1-based page numbers)
page_numbers = [43]

# Output PDF
output_path = r"SQL_Notes_Selected.pdf"

reader = PdfReader(pdf_path)
writer = PdfWriter()

for page_no in page_numbers:
    # Convert 1-based page number to 0-based index
    page_index = page_no - 1

    if 0 <= page_index < len(reader.pages):
        writer.add_page(reader.pages[page_index])
    else:
        print(f"Page {page_no} does not exist.")

with open(output_path, "wb") as output_file:
    writer.write(output_file)

print(f"Done! New PDF created at:\n{output_path}")
