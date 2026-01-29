
import os
import random
import shutil

# Script to generate a "Large" project for stress testing
# 50 Files, ~10 Functions each, Inter-file calls

TARGET_DIR = os.path.join(os.getcwd(), "test_large_project")

def main():
    if os.path.exists(TARGET_DIR):
        shutil.rmtree(TARGET_DIR)
    os.makedirs(TARGET_DIR)
    
    files = [f"module_{i}" for i in range(50)]
    entry_point = "main"
    
    # Create Main Entry
    with open(os.path.join(TARGET_DIR, "main.py"), "w") as f:
        f.write("import module_0\nimport module_1\n\n")
        f.write("def start_app():\n")
        f.write("    print('Starting...')\n")
        f.write("    module_0.func_0()\n")
        f.write("    module_1.func_0()\n")
        
    for i, fname in enumerate(files):
        with open(os.path.join(TARGET_DIR, f"{fname}.py"), "w") as f:
            # Random imports
            imported = random.sample(files, 3) if len(files) > 3 else files
            for imp in imported:
                if imp != fname:
                    f.write(f"import {imp}\n")
            
            f.write("\n")
            
            # 10 Functions per file
            for j in range(10):
                f.write(f"def func_{j}():\n")
                # Random calls to local or imported
                if random.random() > 0.5:
                     target_mod = random.choice(imported)
                     if target_mod != fname:
                         f.write(f"    {target_mod}.func_{random.randint(0, 9)}()\n")
                else:
                     if j < 9:
                         f.write(f"    func_{j+1}()\n")
                     else:
                         f.write("    pass\n")
                f.write("\n")

    print(f"[+] Large project generated at: {TARGET_DIR}")
    print(f"[+] To test: Enter '{TARGET_DIR}' in the Visualizer")

if __name__ == "__main__":
    main()
