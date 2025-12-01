import os
import re
import json
import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # This is PyMuPDF (To read the PDF)
from PIL import Image, ImageTk  # To display images in Tkinter

# Import downloader functions (Task 2 Integration)
try:
    from downloader import download, is_folder_url, download_file, download_folder
    DOWNLOADER_AVAILABLE = True
except ImportError:
    DOWNLOADER_AVAILABLE = False
    print("Warning: downloader.py not found. Download feature will be disabled.")

# Import full text extractor (Task 1 Integration)
try:
    from pdf_extractor import extract_text_from_pdf
    FULL_EXTRACTOR_AVAILABLE = True
except ImportError:
    FULL_EXTRACTOR_AVAILABLE = False
    print("Note: pdf_extractor.py not found. Full extraction disabled.")


class RAGDataTool:
    def __init__(self, root):
        self.root = root
        self.root.title("RAG Data Curator Tool - A/L & O/L Exam Helper")
        self.root.geometry("1400x800")

        # --- 1. Layout Setup (Frames) ---
        # We use a PanedWindow so the user can resize the width of the panels
        self.main_pane = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel: File Tree (Browser)
        self.frame_tree = tk.Frame(self.main_pane, bg="#f0f0f0", width=280)
        self.setup_file_tree()
        self.main_pane.add(self.frame_tree)

        # Middle Panel: PDF Preview
        self.frame_preview = tk.Frame(self.main_pane, bg="#2d2d2d", width=500)
        self.setup_preview_area()
        self.main_pane.add(self.frame_preview)

        # Right Panel: Metadata Input
        self.frame_meta = tk.Frame(self.main_pane, bg="#fafafa", width=420)
        self.setup_metadata_area()
        self.main_pane.add(self.frame_meta)

        # Variables to track state
        self.current_folder = ""
        self.current_file_path = ""
        self.saved_data = []  # Store all saved entries

    # --- UI Components Setup ---

    def setup_file_tree(self):
        # Header
        header = tk.Frame(self.frame_tree, bg="#007acc")
        header.pack(fill=tk.X)
        tk.Label(header, text="📁 File Browser", bg="#007acc", fg="white", 
                 font=("Segoe UI", 11, "bold"), pady=8).pack()

        # Folder Open Button
        btn_open = tk.Button(self.frame_tree, text="📂 Open Folder", 
                             command=self.open_folder, bg="#0e639c", fg="white",
                             font=("Segoe UI", 10), cursor="hand2", relief="flat")
        btn_open.pack(fill=tk.X, padx=8, pady=8)

        # Stats Label
        self.lbl_stats = tk.Label(self.frame_tree, text="No folder selected", 
                                   bg="#f0f0f0", fg="#666", font=("Segoe UI", 9))
        self.lbl_stats.pack(fill=tk.X, padx=8)

        # Frame to contain tree and scrollbar
        tree_frame = tk.Frame(self.frame_tree)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Style for Treeview
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        # Treeview (The list of files)
        self.tree = ttk.Treeview(tree_frame, columns=("status",), show="tree headings")
        self.tree.pack(side="left", fill=tk.BOTH, expand=True)
        self.tree.heading("#0", text="File Name", anchor=tk.W)
        self.tree.heading("status", text="Unicode", anchor=tk.CENTER)
        self.tree.column("status", width=70, anchor=tk.CENTER)

        # Scrollbar for the tree
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Bind the click event
        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)

    def setup_preview_area(self):
        # Header
        header = tk.Frame(self.frame_preview, bg="#1e1e1e")
        header.pack(fill=tk.X)
        self.lbl_preview_title = tk.Label(header, text="PDF Preview", 
                                           bg="#1e1e1e", fg="white",
                                           font=("Segoe UI", 11, "bold"), pady=8)
        self.lbl_preview_title.pack()

        # Page navigation frame
        nav_frame = tk.Frame(self.frame_preview, bg="#2d2d2d")
        nav_frame.pack(fill=tk.X, pady=5)
        
        self.btn_prev_page = tk.Button(nav_frame, text="◀ Prev", command=self.prev_page,
                                        bg="#404040", fg="white", relief="flat")
        self.btn_prev_page.pack(side="left", padx=10)
        
        self.lbl_page_info = tk.Label(nav_frame, text="Page: -/-", bg="#2d2d2d", fg="white")
        self.lbl_page_info.pack(side="left", expand=True)
        
        self.btn_next_page = tk.Button(nav_frame, text="Next ▶", command=self.next_page,
                                        bg="#404040", fg="white", relief="flat")
        self.btn_next_page.pack(side="right", padx=10)

        # Scrollable canvas for the image
        self.canvas_frame = tk.Frame(self.frame_preview, bg="#2d2d2d")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#3d3d3d", highlightthickness=0)
        self.canvas.pack(side="left", fill=tk.BOTH, expand=True)

        self.preview_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", 
                                                command=self.canvas.yview)
        self.preview_scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.preview_scrollbar.set)

        # Variables for page navigation
        self.current_page = 0
        self.total_pages = 0
        self.current_doc = None

    def setup_metadata_area(self):
        # Header
        header = tk.Frame(self.frame_meta, bg="#28a745")
        header.pack(fill=tk.X)
        tk.Label(header, text="📝 Metadata Entry", bg="#28a745", fg="white",
                 font=("Segoe UI", 11, "bold"), pady=8).pack()

        # Unicode Status Indicator
        self.unicode_frame = tk.Frame(self.frame_meta, bg="#fafafa")
        self.unicode_frame.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_unicode_status = tk.Label(self.unicode_frame, text="Unicode Status: Not Checked",
                                            bg="#fafafa", font=("Segoe UI", 10, "bold"))
        self.lbl_unicode_status.pack(anchor="w")

        # Scrollable frame for form fields
        form_canvas = tk.Canvas(self.frame_meta, bg="#fafafa", highlightthickness=0)
        form_scrollbar = ttk.Scrollbar(self.frame_meta, orient="vertical", command=form_canvas.yview)
        self.form_frame = tk.Frame(form_canvas, bg="#fafafa")

        self.form_frame.bind("<Configure>", lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        form_canvas.pack(side="left", fill=tk.BOTH, expand=True, padx=10, pady=5)
        form_scrollbar.pack(side="right", fill="y")

        # Exam Level Selection (A/L or O/L)
        tk.Label(self.form_frame, text="Exam Level:", bg="#fafafa", 
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 2))
        self.exam_level = tk.StringVar(value="A/L")
        level_frame = tk.Frame(self.form_frame, bg="#fafafa")
        level_frame.pack(fill=tk.X, pady=2)
        tk.Radiobutton(level_frame, text="A/L", variable=self.exam_level, value="A/L",
                       bg="#fafafa", font=("Segoe UI", 10)).pack(side="left")
        tk.Radiobutton(level_frame, text="O/L", variable=self.exam_level, value="O/L",
                       bg="#fafafa", font=("Segoe UI", 10)).pack(side="left", padx=20)

        # Subject Dropdown
        tk.Label(self.form_frame, text="Subject:", bg="#fafafa", 
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 2))
        self.cmb_subject = ttk.Combobox(self.form_frame, font=("Segoe UI", 10), state="readonly")
        self.cmb_subject['values'] = (
            "Combined Mathematics", "Physics", "Chemistry", "Biology",
            "ICT", "Economics", "Business Studies", "Accounting",
            "Sinhala", "English", "Tamil", "Buddhism", "History",
            "Political Science", "Geography", "Art", "Music", "Other"
        )
        self.cmb_subject.pack(fill=tk.X, pady=2)

        # Year Input
        tk.Label(self.form_frame, text="Year:", bg="#fafafa", 
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 2))
        self.ent_year = tk.Entry(self.form_frame, font=("Segoe UI", 10))
        self.ent_year.pack(fill=tk.X, pady=2)

        # Paper Type
        tk.Label(self.form_frame, text="Paper Type:", bg="#fafafa", 
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 2))
        self.cmb_paper_type = ttk.Combobox(self.form_frame, font=("Segoe UI", 10), state="readonly")
        self.cmb_paper_type['values'] = (
            "Past Paper", "Model Paper", "Notes", "Tutorial", 
            "Marking Scheme", "Syllabus", "Other"
        )
        self.cmb_paper_type.pack(fill=tk.X, pady=2)

        # Source URL
        tk.Label(self.form_frame, text="Source URL (Google Drive Link):", bg="#fafafa",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 2))
        
        # URL Entry
        self.ent_source_url = tk.Entry(self.form_frame, font=("Segoe UI", 10))
        self.ent_source_url.pack(fill=tk.X, pady=2)
        
        # Download Button (on its own row for visibility)
        download_frame = tk.Frame(self.form_frame, bg="#fafafa")
        download_frame.pack(fill=tk.X, pady=(5, 2))
        
        self.btn_download = tk.Button(download_frame, text="Download from Google Drive", 
                                       command=self.download_from_drive,
                                       bg="#4285F4", fg="white", font=("Segoe UI", 10, "bold"),
                                       cursor="hand2", relief="flat", padx=15, pady=5)
        self.btn_download.pack(side="left")
        
        # Download Status Label
        self.lbl_download_status = tk.Label(download_frame, text="", bg="#fafafa", 
                                             font=("Segoe UI", 9), fg="#666")
        self.lbl_download_status.pack(side="left", padx=(10, 0))

        # Extracted Text / Notes
        tk.Label(self.form_frame, text="Extracted Text Preview:", bg="#fafafa",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 2))
        
        # Extraction mode buttons (Task 1 Integration)
        extract_frame = tk.Frame(self.form_frame, bg="#fafafa")
        extract_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(extract_frame, text="Extract:", bg="#fafafa", 
                 font=("Segoe UI", 9), fg="#666").pack(side="left")
        
        self.btn_quick_extract = tk.Button(extract_frame, text="Quick (3 pages)", 
                              command=self.extract_and_display_text,
                              bg="#6c757d", fg="white", font=("Segoe UI", 9),
                              relief="flat", padx=10, pady=2, cursor="hand2")
        self.btn_quick_extract.pack(side="left", padx=(8, 3))
        
        self.btn_full_extract = tk.Button(extract_frame, text="Full (All pages)", 
                             command=self.extract_full_text,
                             bg="#fd7e14", fg="white", font=("Segoe UI", 9),
                             relief="flat", padx=10, pady=2, cursor="hand2")
        self.btn_full_extract.pack(side="left", padx=3)
        
        # Extraction status label
        self.lbl_extract_status = tk.Label(extract_frame, text="", bg="#fafafa", 
                                            font=("Segoe UI", 8), fg="#666")
        self.lbl_extract_status.pack(side="left", padx=(10, 0))
        
        self.txt_content = tk.Text(self.form_frame, height=12, bg="#fffef0", 
                                    font=("Consolas", 10), wrap=tk.WORD)
        self.txt_content.pack(fill=tk.BOTH, expand=True, pady=2)

        # Additional Notes
        tk.Label(self.form_frame, text="Additional Notes:", bg="#fafafa",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 2))
        self.txt_notes = tk.Text(self.form_frame, height=4, bg="white", 
                                  font=("Segoe UI", 10), wrap=tk.WORD)
        self.txt_notes.pack(fill=tk.BOTH, pady=2)

        # Separator
        ttk.Separator(self.form_frame, orient="horizontal").pack(fill=tk.X, pady=15)

        # Button Frame (inside scrollable form)
        btn_frame = tk.Frame(self.form_frame, bg="#fafafa")
        btn_frame.pack(fill=tk.X, pady=5)

        # Check Unicode Button
        btn_check = tk.Button(btn_frame, text="Check Unicode", command=self.check_unicode,
                              bg="#17a2b8", fg="white", font=("Segoe UI", 10, "bold"),
                              cursor="hand2", relief="flat", pady=8)
        btn_check.pack(side="left", fill=tk.X, expand=True, padx=(0, 5))

        # Save Button
        btn_save = tk.Button(btn_frame, text="Save Entry", command=self.save_metadata,
                             bg="#28a745", fg="white", font=("Segoe UI", 10, "bold"),
                             cursor="hand2", relief="flat", pady=8)
        btn_save.pack(side="left", fill=tk.X, expand=True, padx=(5, 0))

        # Export Button
        btn_export = tk.Button(self.form_frame, text="Export to CSV (for Google Sheets)",
                               command=self.export_to_csv, bg="#6c757d", fg="white",
                               font=("Segoe UI", 10), cursor="hand2", relief="flat", pady=8)
        btn_export.pack(fill=tk.X, pady=(10, 20))

    # --- Application Logic ---

    def open_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.current_folder = folder_path
            self.load_files()

    def download_from_drive(self):
        """Download file/folder from Google Drive URL (Task 2 Integration)"""
        if not DOWNLOADER_AVAILABLE:
            messagebox.showerror("Error", 
                "Downloader module not available!\n\n"
                "Make sure 'downloader.py' is in the same folder as this application.")
            return
        
        url = self.ent_source_url.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a Google Drive URL first.")
            return
        
        # Check if we have a folder selected, if not ask for one
        if not self.current_folder:
            self.current_folder = filedialog.askdirectory(title="Select Download Destination")
            if not self.current_folder:
                return
        
        # Confirm download
        is_folder = is_folder_url(url)
        item_type = "folder" if is_folder else "file"
        
        confirm = messagebox.askyesno("Confirm Download", 
            f"Download this {item_type} to:\n{self.current_folder}\n\nContinue?")
        
        if not confirm:
            return
        
        # Update UI for download in progress
        self.btn_download.config(state="disabled", text="Downloading...")
        self.lbl_download_status.config(text="Downloading... Please wait.", fg="#17a2b8")
        self.root.update()
        
        # Run download in a separate thread to keep UI responsive
        download_thread = threading.Thread(target=self._perform_download, args=(url,))
        download_thread.start()
    
    def _perform_download(self, url):
        """Perform the actual download in a background thread"""
        try:
            success = download(url, self.current_folder)
            
            # Update UI on main thread
            self.root.after(0, lambda: self._download_complete(success))
            
        except Exception as e:
            self.root.after(0, lambda: self._download_error(str(e)))
    
    def _download_complete(self, success):
        """Handle download completion on main thread"""
        self.btn_download.config(state="normal", text="Download")
        
        if success:
            self.lbl_download_status.config(text="✅ Download complete!", fg="#28a745")
            self.load_files()  # Refresh file tree
            messagebox.showinfo("Success", 
                "Download complete!\n\nThe file list has been refreshed.")
        else:
            self.lbl_download_status.config(text="❌ Download failed", fg="#dc3545")
            messagebox.showerror("Download Failed", 
                "Could not download the file/folder.\n\n"
                "Possible reasons:\n"
                "• The link is private (not shared)\n"
                "• The link is invalid\n"
                "• Network connection issue\n\n"
                "Check console for details.")
    
    def _download_error(self, error_msg):
        """Handle download error on main thread"""
        self.btn_download.config(state="normal", text="Download")
        self.lbl_download_status.config(text="❌ Error occurred", fg="#dc3545")
        messagebox.showerror("Error", f"Download error:\n{error_msg}")

    def load_files(self):
        # Clear the current tree list
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Loop through files and add PDFs to the list
        try:
            pdf_count = 0
            for file_name in os.listdir(self.current_folder):
                if file_name.lower().endswith(".pdf"):
                    self.tree.insert("", tk.END, text=file_name, values=("?",))
                    pdf_count += 1
            
            self.lbl_stats.config(text=f"📄 {pdf_count} PDF files found")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_file_select(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return

        file_name = self.tree.item(selected_item)['text']
        self.current_file_path = os.path.join(self.current_folder, file_name)

        # Update preview title
        self.lbl_preview_title.config(text=f"Preview: {file_name[:40]}...")

        # Reset page navigation
        self.current_page = 0

        # Close previous document if open
        if self.current_doc:
            self.current_doc.close()
            self.current_doc = None

        # Show the PDF Preview
        self.render_pdf_preview(self.current_file_path)

        # Extract and display text (Dev Task 1 Integration)
        self.extract_and_display_text()
        
        # Auto-check Unicode status
        self.root.after(100, self.check_unicode)  # Small delay to ensure text is loaded

    def render_pdf_preview(self, pdf_path):
        try:
            # Open the PDF using PyMuPDF
            self.current_doc = fitz.open(pdf_path)
            self.total_pages = len(self.current_doc)
            self.render_current_page()
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(250, 200, text=f"Preview Error:\n{e}", 
                                    fill="white", font=("Segoe UI", 12))

    def render_current_page(self):
        if not self.current_doc:
            return

        try:
            page = self.current_doc.load_page(self.current_page)

            # Scale to fit canvas (adjust for high DPI if needed)
            mat = fitz.Matrix(1.0, 1.0)
            pix = page.get_pixmap(matrix=mat)

            img_data = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            self.tk_img = ImageTk.PhotoImage(img_data)

            # Clear and add new image
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
            self.canvas.configure(scrollregion=(0, 0, pix.width, pix.height))

            # Update page info
            self.lbl_page_info.config(text=f"Page: {self.current_page + 1}/{self.total_pages}")

            pix = None

        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(250, 200, text=f"Error: {e}", fill="white")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_current_page()

    def next_page(self):
        if self.current_doc and self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.render_current_page()

    def extract_and_display_text(self):
        """Quick extraction - Extract text from first 3 pages (PyMuPDF)"""
        if not self.current_file_path:
            return

        try:
            doc = fitz.open(self.current_file_path)
            text = ""
            pages_extracted = min(3, len(doc))
            # Extract text from first few pages (limit for preview)
            for page_num in range(pages_extracted):
                page = doc.load_page(page_num)
                text += page.get_text() + "\n\n"
            doc.close()

            # Update the text area
            self.txt_content.delete("1.0", tk.END)
            if text.strip():
                self.txt_content.insert("1.0", text[:5000])  # Limit preview length
                self.lbl_extract_status.config(text=f"(Quick: {pages_extracted} pages)", fg="#6c757d")
            else:
                self.txt_content.insert("1.0", "(No extractable text found - might be scanned PDF)")
                self.lbl_extract_status.config(text="", fg="#666")

        except Exception as e:
            self.txt_content.delete("1.0", tk.END)
            self.txt_content.insert("1.0", f"Error extracting text: {e}")
            self.lbl_extract_status.config(text="", fg="#666")

    def extract_full_text(self):
        """Full extraction - Extract ALL pages using teammate's extractor (Task 1)"""
        if not self.current_file_path:
            messagebox.showwarning("Warning", "Please select a PDF file first.")
            return
        
        if not FULL_EXTRACTOR_AVAILABLE:
            messagebox.showerror("Error", 
                "Full extractor not available!\n\n"
                "Make sure 'pdf_extractor.py' is in the same folder.\n"
                "Also install: pip install pdfplumber PyPDF2")
            return
        
        try:
            # Show loading message
            self.txt_content.delete("1.0", tk.END)
            self.txt_content.insert("1.0", "Extracting all pages... Please wait.")
            self.lbl_extract_status.config(text="Extracting...", fg="#fd7e14")
            self.btn_full_extract.config(state="disabled")
            self.root.update()
            
            # Use teammate's extractor (pdfplumber)
            full_text = extract_text_from_pdf(self.current_file_path)
            
            # Count pages extracted
            page_count = full_text.count("--- Page")
            
            # Display result
            self.txt_content.delete("1.0", tk.END)
            if full_text and not full_text.startswith("Error"):
                self.txt_content.insert("1.0", full_text)
                self.lbl_extract_status.config(text=f"(Full: {page_count} pages)", fg="#fd7e14")
            else:
                self.txt_content.insert("1.0", f"Extraction failed: {full_text}")
                self.lbl_extract_status.config(text="Failed", fg="#dc3545")
            
            # Re-check Unicode with full text
            self.check_unicode()
            
        except Exception as e:
            self.txt_content.delete("1.0", tk.END)
            self.txt_content.insert("1.0", f"Error: {e}")
            self.lbl_extract_status.config(text="Error", fg="#dc3545")
        finally:
            self.btn_full_extract.config(state="normal")

    def check_unicode(self):
        """Check if the extracted text contains valid Unicode (Sinhala/Tamil support)"""
        text = self.txt_content.get("1.0", tk.END).strip()

        if not text or text.startswith("(No extractable") or text.startswith("Error"):
            self.lbl_unicode_status.config(text="⚠️ Unicode Status: Cannot Check (No text)", 
                                           fg="#dc3545")
            self.update_tree_status("⚠️")
            return

        # Check for Sinhala Unicode range (U+0D80 to U+0DFF)
        has_sinhala = any('\u0D80' <= char <= '\u0DFF' for char in text)
        
        # Check for Tamil Unicode range (U+0B80 to U+0BFF)
        has_tamil = any('\u0B80' <= char <= '\u0BFF' for char in text)
        
        # Check for LEGACY Sinhala font encoding (FM fonts, etc.)
        # These fonts use ASCII characters that LOOK like Sinhala but aren't real Unicode
        is_legacy_font = self.detect_legacy_sinhala_font(text)
        
        # Check for common printable characters (basic validation)
        has_readable = any(char.isalpha() for char in text)

        if has_sinhala:
            self.lbl_unicode_status.config(text="✅ Unicode Status: VALID (Sinhala Unicode)", 
                                           fg="#28a745")
            self.update_tree_status("✅")
        elif has_tamil:
            self.lbl_unicode_status.config(text="✅ Unicode Status: VALID (Tamil Unicode)", 
                                           fg="#28a745")
            self.update_tree_status("✅")
        elif is_legacy_font:
            self.lbl_unicode_status.config(
                text="❌ Unicode Status: INVALID (Legacy Sinhala Font - NOT usable)", 
                fg="#dc3545")
            self.update_tree_status("❌")
        elif has_readable:
            self.lbl_unicode_status.config(text="✅ Unicode Status: VALID (English/Latin)", 
                                           fg="#28a745")
            self.update_tree_status("✅")
        else:
            self.lbl_unicode_status.config(text="❌ Unicode Status: INVALID (Unreadable)", 
                                           fg="#dc3545")
            self.update_tree_status("❌")

    def detect_legacy_sinhala_font(self, text):
        """
        Detect if text is encoded with legacy Sinhala fonts (FM, DL, Kaputa, etc.)
        These fonts map ASCII characters to Sinhala glyphs visually, but the actual
        text is gibberish when extracted.
        
        Key indicators:
        1. High frequency of semicolons (;) - used for vowel signs in FM fonts
        2. Extended Latin chars (ú, ñ, ä, ï, etc.) - common in legacy fonts
        3. Percentage signs (%) mixed with text
        4. Random-looking character sequences
        5. NO actual Sinhala Unicode present
        """
        if not text or len(text) < 20:
            return False
        
        # If it already has real Sinhala Unicode, it's not legacy
        has_real_sinhala = any('\u0D80' <= char <= '\u0DFF' for char in text)
        if has_real_sinhala:
            return False
        
        # Count indicators of legacy font encoding
        total_chars = len(text)
        
        # Indicator 1: High semicolon frequency (FM fonts use ; extensively)
        semicolon_count = text.count(';')
        semicolon_ratio = semicolon_count / total_chars
        
        # Indicator 2: Extended Latin characters common in FM/DL fonts
        legacy_chars = set('úñäïöüabordfghjklzxcvbnmqwertyuiopWIKLMNBVCXZJHGFDSAPQERTYUO')
        extended_latin = set('úñäïöüÿàáâãåæçèéêëìíîðòóôõøùûýþ')
        extended_count = sum(1 for c in text if c in extended_latin)
        
        # Indicator 3: Percentage signs mixed in
        percent_count = text.count('%')
        
        # Indicator 4: Pattern detection - semicolon after letters (like "WIaK;ajh")
        legacy_pattern = re.findall(r'[a-zA-Z]+[;%][a-zA-Z]+', text)
        pattern_matches = len(legacy_pattern)
        
        # Indicator 5: Check for common FM font character combinations
        fm_patterns = [';a', ';s', ';j', ';d', ';l', ';k', 'ú', 'ñ', 'ï', 'ä', 
                       'WIaK', 'fld', 'fjk', 'lrk', 'mq', 'mqr', 'iaj', 'mdv']
        fm_pattern_count = sum(1 for p in fm_patterns if p in text)
        
        # Decision logic
        # If multiple indicators are present, it's likely legacy font
        score = 0
        
        if semicolon_ratio > 0.03:  # More than 3% semicolons
            score += 2
        if extended_count > 3:
            score += 1
        if percent_count > 2:
            score += 1
        if pattern_matches > 3:
            score += 2
        if fm_pattern_count >= 3:
            score += 3
            
        # High confidence if score >= 3
        return score >= 3

    def update_tree_status(self, status):
        """Update the Unicode status column in the file tree"""
        selected_item = self.tree.selection()
        if selected_item:
            self.tree.item(selected_item, values=(status,))

    def save_metadata(self):
        if not self.current_file_path:
            messagebox.showwarning("Warning", "Please select a file first.")
            return

        subject = self.cmb_subject.get()
        if not subject:
            messagebox.showwarning("Warning", "Please select a subject.")
            return

        # Get full extracted text
        full_text = self.txt_content.get("1.0", tk.END).strip()
        
        # Save full text to separate file (for RAG pipeline)
        text_file_path = self.save_extracted_text(full_text)
        
        # Get extraction mode from status label
        extract_status = self.lbl_extract_status.cget("text")
        extraction_mode = "full" if "Full" in extract_status else "quick"

        # Collect all metadata
        entry = {
            "file_name": os.path.basename(self.current_file_path),
            "file_path": self.current_file_path,
            "exam_level": self.exam_level.get(),
            "subject": subject,
            "year": self.ent_year.get(),
            "paper_type": self.cmb_paper_type.get(),
            "source_url": self.ent_source_url.get(),
            "unicode_status": self.lbl_unicode_status.cget("text"),
            "notes": self.txt_notes.get("1.0", tk.END).strip(),
            "text_preview": self.txt_content.get("1.0", "3.0").strip(),  # First 3 lines for display
            "extracted_text_file": text_file_path,  # Reference to full text file
            "extraction_mode": extraction_mode,  # quick or full
            "text_length": len(full_text)  # Character count for reference
        }

        self.saved_data.append(entry)

        # Also save to JSON file
        self.save_to_json()

        messagebox.showinfo("Success", 
            f"✅ Entry saved!\n\n"
            f"Total entries: {len(self.saved_data)}\n"
            f"Full text saved to:\n{text_file_path}")
    
    def save_extracted_text(self, text):
        """Save full extracted text to a separate file for RAG pipeline"""
        # Create 'extracted_texts' folder if it doesn't exist
        extracted_folder = os.path.join(self.current_folder, "extracted_texts")
        if not os.path.exists(extracted_folder):
            os.makedirs(extracted_folder)
        
        # Generate filename from PDF name
        pdf_name = os.path.basename(self.current_file_path)
        txt_name = os.path.splitext(pdf_name)[0] + "_extracted.txt"
        txt_path = os.path.join(extracted_folder, txt_name)
        
        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                # Add header with metadata
                f.write(f"# Source: {pdf_name}\n")
                f.write(f"# Exam Level: {self.exam_level.get()}\n")
                f.write(f"# Subject: {self.cmb_subject.get()}\n")
                f.write(f"# Year: {self.ent_year.get()}\n")
                f.write(f"# Paper Type: {self.cmb_paper_type.get()}\n")
                f.write(f"# Unicode Status: {self.lbl_unicode_status.cget('text')}\n")
                f.write(f"# Extracted: {self.lbl_extract_status.cget('text')}\n")
                f.write("#" + "="*50 + "\n\n")
                f.write(text)
            return txt_path
        except Exception as e:
            print(f"Error saving extracted text: {e}")
            return None

    def save_to_json(self):
        """Save all entries to a JSON file"""
        json_path = os.path.join(self.current_folder, "rag_metadata.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.saved_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving JSON: {e}")

    def export_to_csv(self):
        """Export saved data to CSV for Google Sheets import"""
        if not self.saved_data:
            messagebox.showwarning("Warning", "No data to export. Save some entries first.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfilename="rag_data_export.csv"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "file_name", "exam_level", "subject", "year", 
                    "paper_type", "source_url", "unicode_status", "notes"
                ])
                writer.writeheader()
                for entry in self.saved_data:
                    # Write subset of fields (excluding large text)
                    row = {k: entry.get(k, "") for k in writer.fieldnames}
                    writer.writerow(row)

            messagebox.showinfo("Success", f"✅ Exported {len(self.saved_data)} entries to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")


# --- Run the Application ---
if __name__ == "__main__":
    root = tk.Tk()
    app = RAGDataTool(root)
    root.mainloop()
