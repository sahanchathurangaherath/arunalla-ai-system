import gdown
import os
import re
import sys
import requests
from bs4 import BeautifulSoup


def extract_file_id(url):
    """Extract file ID from Google Drive URL"""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'^([a-zA-Z0-9_-]+)$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_folder_id(url):
    """Extract folder ID from Google Drive URL"""
    patterns = [
        r'/folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_folder_url(url):
    """Check if URL is a folder URL"""
    return '/folders/' in url


def sanitize_filename(name):
    """Remove invalid characters from filename/folder name for Windows"""
    # Replace invalid Windows characters: \ / : * ? " < > |
    invalid_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(invalid_chars, '_', name)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    return sanitized if sanitized else "unnamed_folder"


def get_unique_path(path):
    """Get a unique path by adding (1), (2), etc. if path already exists"""
    if not os.path.exists(path):
        return path
    
    base_path = path
    counter = 1
    
    # For files with extension
    if '.' in os.path.basename(path):
        name, ext = os.path.splitext(path)
        while os.path.exists(path):
            path = f"{name} ({counter}){ext}"
            counter += 1
    else:
        # For folders or files without extension
        while os.path.exists(path):
            path = f"{base_path} ({counter})"
            counter += 1
    
    return path


def get_folder_name(folder_id):
    """Get folder name from Google Drive"""
    try:
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                
                # Check if it's a sign-in page (private folder)
                if "Sign-in" in title or "sign in" in title.lower():
                    return None  # Indicates private folder
                
                # Remove " - Google Drive" suffix
                if " - Google Drive" in title:
                    title = title.replace(" - Google Drive", "").strip()
                
                # Sanitize the folder name for Windows
                return sanitize_filename(title) if title else None
                
    except Exception as e:
        print(f"Could not get folder name: {e}")
    
    return f"folder_{folder_id[:8]}"  # Return short folder ID as fallback


def download_folder(url, output_folder):
    """Download all files from a Google Drive folder with folder name preserved"""
    folder_id = extract_folder_id(url)
    
    if not folder_id:
        print(f"Error: Could not extract folder ID from URL: {url}")
        return False
    
    # Get the folder name from Google Drive
    folder_name = get_folder_name(folder_id)
    
    # Check if folder is private/inaccessible
    if folder_name is None:
        print("\n" + "=" * 50)
        print("ERROR: Cannot access this folder!")
        print("=" * 50)
        print("Possible reasons:")
        print("  1. The folder is PRIVATE (not shared)")
        print("  2. The folder requires sign-in")
        print("  3. The folder doesn't exist")
        print("  4. The link is invalid")
        print("\nSolution:")
        print("  - Ask the owner to share the folder")
        print("  - Set folder to 'Anyone with the link' can view")
        print("=" * 50 + "\n")
        return False
    
    print(f"Folder name: {folder_name}")
    
    # Create output path with folder name (e.g., downloads/Testing/)
    final_output = os.path.join(output_folder, folder_name)
    
    # Get unique path if folder already exists (adds (1), (2), etc.)
    final_output = get_unique_path(final_output)
    
    # Create output folder if it doesn't exist
    if not os.path.exists(final_output):
        os.makedirs(final_output)
        print(f"Created folder: {final_output}")
    
    try:
        print(f"Downloading folder ID: {folder_id}")
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        gdown.download_folder(folder_url, output=final_output, quiet=False)
        print(f"\nSuccessfully downloaded folder to: {final_output}")
        return True
            
    except Exception as e:
        error_msg = str(e).lower()
        if "permission" in error_msg or "access" in error_msg:
            print("\n" + "=" * 50)
            print("ERROR: Permission denied!")
            print("=" * 50)
            print("The folder exists but you don't have access.")
            print("Ask the owner to change sharing settings to:")
            print("  'Anyone with the link' can view")
            print("=" * 50 + "\n")
        else:
            print(f"Error downloading folder: {e}")
        return False


def download_file(url, output_folder):
    """Download a file from Google Drive"""
    file_id = extract_file_id(url)
    
    if not file_id:
        print(f"Error: Could not extract file ID from URL: {url}")
        return False
    
    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created folder: {output_folder}")
    
    # Construct download URL
    download_url = f"https://drive.google.com/uc?id={file_id}"
    
    try:
        print(f"Downloading file ID: {file_id}")
        output_path = gdown.download(download_url, output=output_folder + os.sep, fuzzy=True)
        
        if output_path:
            print(f"Successfully downloaded: {output_path}")
            return True
        else:
            print("\n" + "=" * 50)
            print("ERROR: Download failed!")
            print("=" * 50)
            print("Possible reasons:")
            print("  1. The file is PRIVATE")
            print("  2. The file requires sign-in")
            print("  3. The file doesn't exist")
            print("\nSolution:")
            print("  - Ask the owner to share the file")
            print("  - Set file to 'Anyone with the link' can view")
            print("=" * 50 + "\n")
            return False
            
    except Exception as e:
        error_msg = str(e).lower()
        if "permission" in error_msg or "access" in error_msg or "denied" in error_msg:
            print("\n" + "=" * 50)
            print("ERROR: Permission denied!")
            print("=" * 50)
            print("The file is private or requires sign-in.")
            print("Ask the owner to share the file with:")
            print("  'Anyone with the link' can view")
            print("=" * 50 + "\n")
        else:
            print(f"Error downloading file: {e}")
        return False


def download(url, output_folder):
    """Download file or folder based on URL type"""
    url = url.strip()
    
    if is_folder_url(url):
        print("Detected: FOLDER URL")
        return download_folder(url, output_folder)
    else:
        print("Detected: FILE URL")
        return download_file(url, output_folder)


def main():
    print("=" * 50)
    print("Google Drive File/Folder Downloader")
    print("=" * 50)
    
    # Get output folder
    output_folder = input("\nEnter output folder path (or press Enter for 'downloads'): ").strip()
    if not output_folder:
        output_folder = "downloads"
    
    while True:
        print("\n" + "=" * 50)
        print("OPTIONS:")
        print("=" * 50)
        print("1. Download files/folders from ONE Google Drive link")
        print("2. Download files/folders from MULTIPLE Google Drive links")
        print("3. Exit")
        print("=" * 50)
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            print("\n[Single Link Download]")
            print("-" * 30)
            url = input("Enter Google Drive URL (file or folder): ").strip()
            if url:
                download(url, output_folder)
            else:
                print("No URL provided!")
                
        elif choice == "2":
            print("\n[Multiple Links Download]")
            print("-" * 30)
            print("Enter Google Drive URLs (one per line)")
            print("Press Enter on empty line when finished:")
            print()
            urls = []
            count = 1
            while True:
                url = input(f"  Link {count}: ").strip()
                if not url:
                    break
                urls.append(url)
                count += 1
            
            if urls:
                print(f"\n{'=' * 50}")
                print(f"Starting download of {len(urls)} items...")
                print(f"{'=' * 50}")
                
                success_count = 0
                fail_count = 0
                
                for i, url in enumerate(urls, 1):
                    print(f"\n[{i}/{len(urls)}] Downloading...")
                    print("-" * 30)
                    if download(url, output_folder):
                        success_count += 1
                    else:
                        fail_count += 1
                
                # Summary
                print(f"\n{'=' * 50}")
                print("DOWNLOAD SUMMARY")
                print(f"{'=' * 50}")
                print(f"  Total: {len(urls)}")
                print(f"  Success: {success_count}")
                print(f"  Failed: {fail_count}")
                print(f"{'=' * 50}")
            else:
                print("No URLs provided!")
                
        elif choice == "3":
            print("\nGoodbye! Thank you for using Google Drive Downloader.")
            break
        else:
            print("Invalid choice! Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()
