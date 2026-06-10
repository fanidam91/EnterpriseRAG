import zipfile
import os

def main():
    zip_path = "notebooks.zip"
    notebooks_dir = "notebooks"
    print(f"Creating/updating {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in os.listdir(notebooks_dir):
            if f.endswith(".py"):
                file_path = os.path.join(notebooks_dir, f)
                print(f"  Adding {file_path} as {f}")
                z.write(file_path, f)
    print("Regeneration complete!")

if __name__ == "__main__":
    main()
